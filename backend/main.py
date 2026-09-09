"""HTTP application for the private Sheetwise workspace."""
import asyncio
import csv
import os
import random
import tempfile
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .agent import answer_question, configured, model_name
from .auth import Sessions
from .ingest import MAX_BYTES, ingest_file, preview_rows
from .presentation import dashboard
from .store import Store
from .limits import RequestBounds

ROOT=Path(__file__).resolve().parents[1]


class LoginRequest(BaseModel):
    password: str=Field(min_length=1,max_length=256)


class ChatRequest(BaseModel):
    question: str=Field(min_length=1,max_length=2000)


class PinRequest(BaseModel):
    answerId: str=Field(pattern=r'^[0-9a-f-]{36}$')
    pinned: bool=True


def error(status,code,message):
    return JSONResponse({'error':{'code':code,'message':message,'requestId':str(uuid.uuid4())}},status_code=status)


def public_profile(profile, full=True):
    result={k:v for k,v in profile.items() if k!='databasePath'}
    if full:
        result['dashboard']=dashboard(profile)
    else:
        result.pop('columns',None)
        result.pop('warnings',None)
    return result


def create_app(data_dir=None, local_mode=None):
    root=Path(data_dir or os.getenv('DATA_DIR',ROOT/'.data')).resolve()
    password=os.getenv('WORKSPACE_PASSWORD','')
    local_mode=(os.getenv('APP_HOST','127.0.0.1') in ('localhost','127.0.0.1','::1')) if local_mode is None else local_mode
    if not password and not local_mode:
        raise ValueError('WORKSPACE_PASSWORD is required for non-loopback deployment.')
    store=Store(root)
    sessions=Sessions(root,password)
    app=FastAPI(title='Sheetwise API',version='1.0.0',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store
    app.add_middleware(RequestBounds)
    upload_gate=threading.BoundedSemaphore(1)
    chat_gate=threading.BoundedSemaphore(2)

    @app.middleware('http')
    async def workspace_boundary(request:Request,call_next):
        if request.url.path.startswith('/api/'):
            trusted_hosts={'localhost','127.0.0.1','::1'}
            if request.client and request.client.host=='testclient':
                trusted_hosts.add('testserver')
            if not password and request.url.hostname not in trusted_hosts:
                return error(403,'HOST_REJECTED','Local mode only accepts a localhost address.')
            content_length=request.headers.get('content-length','0')
            if not content_length.isdigit():
                return error(400,'INVALID_REQUEST','Invalid request length.')
            if int(content_length)>MAX_BYTES+1024*1024:
                return error(413,'FILE_TOO_LARGE','Files must be 100 MB or smaller.')
            origin=request.headers.get('origin')
            if request.method not in ('GET','HEAD','OPTIONS') and origin and urlparse(origin).netloc!=request.headers.get('host'):
                return error(403,'ORIGIN_REJECTED','This action must come from the workspace app.')
            if request.url.path not in ('/api/status','/api/session'):
                if password and not sessions.valid(request.cookies.get('sheetwise_session')):
                    return error(401,'UNAUTHORIZED','Enter the workspace password to continue.')
                if not password and request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
                    return error(401,'UNAUTHORIZED','Remote access requires a workspace password.')
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(ValueError)
    async def value_error(request,exc):
        return error(400,'INVALID_REQUEST',str(exc))

    @app.exception_handler(KeyError)
    async def not_found(request,exc):
        return error(404,'NOT_FOUND','The requested dataset or answer was not found.')

    @app.exception_handler(RuntimeError)
    async def service_error(request,exc):
        return error(503,'SERVICE_UNAVAILABLE',str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return error(400,'INVALID_REQUEST','Check the required fields, field lengths, and allowed values.')

    @app.exception_handler(Exception)
    async def unexpected_error(request,exc):
        return error(500,'INTERNAL_ERROR','The request could not be completed. Please try again.')

    def profile_for(dataset_id):
        try:
            uuid.UUID(dataset_id)
        except ValueError:
            raise ValueError('Choose a valid dataset.') from None
        return store.dataset(dataset_id)

    @app.get('/api/status',operation_id='getWorkspaceStatus')
    def status(request:Request):
        return {'authenticated':not password or sessions.valid(request.cookies.get('sheetwise_session')),'passwordRequired':bool(password),'aiConfigured':configured(),'model':model_name(),'maxUploadBytes':MAX_BYTES,'localMode':local_mode}

    @app.post('/api/session',operation_id='createWorkspaceSession')
    def login(body:LoginRequest,request:Request):
        if password and not sessions.login(body.password,request.client.host if request.client else 'unknown'):
            return error(401,'UNAUTHORIZED','That password is incorrect.')
        response=JSONResponse({'authenticated':True})
        response.set_cookie('sheetwise_session',sessions.issue(),httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false').lower()=='true',max_age=86400*7)
        return response

    @app.delete('/api/session',operation_id='deleteWorkspaceSession')
    def logout():
        response=JSONResponse({'authenticated':False})
        response.delete_cookie('sheetwise_session')
        return response

    @app.get('/api/datasets',operation_id='listDatasets')
    def datasets():
        return [public_profile(p,False) for p in store.datasets()]

    @app.post('/api/datasets',status_code=201,operation_id='uploadDataset')
    async def upload(file:UploadFile=File(...),sheetName:str|None=Form(None)):
        if not upload_gate.acquire(blocking=False):
            return error(429,'IMPORT_BUSY','Another file is being imported. Try again shortly.')
        temp=None
        try:
            with tempfile.NamedTemporaryFile(dir=root,suffix='.upload',delete=False) as out:
                temp=Path(out.name)
                total=0
                while chunk:=await file.read(1024*1024):
                    total+=len(chunk)
                    if total>MAX_BYTES:
                        return error(413,'FILE_TOO_LARGE','Files must be 100 MB or smaller.')
                    out.write(chunk)
            profile=await run_in_threadpool(ingest_file,temp,file.filename or 'table.csv',root,sheetName)
            store.save_dataset(profile)
            return public_profile(profile)
        finally:
            if temp:
                temp.unlink(missing_ok=True)
            await file.close()
            upload_gate.release()

    @app.post('/api/demo',status_code=201,operation_id='createDemoDataset')
    def demo():
        # Synthetic, deterministic and clearly labeled. No customer data is bundled.
        if not upload_gate.acquire(blocking=False):
            return error(429,'IMPORT_BUSY','Another file is being imported. Try again shortly.')
        try:
            with tempfile.TemporaryDirectory(dir=root) as directory:
                path=Path(directory)/'Demo · Customer acquisition.csv'
                rng=random.Random(42)
                with path.open('w',newline='') as file:
                    writer=csv.writer(file)
                    writer.writerow(['user_id','channel','lead_status','campaign','is_qualified','is_converted','region','language','created_date','order_value'])
                    for i in range(1280):
                        qualified=rng.random()<.61
                        converted=qualified and rng.random()<.37
                        writer.writerow([f'U{i+1:05}',rng.choices(['WhatsApp','Instagram','Website','Facebook'],[45,27,18,10])[0],rng.choices(['Hot','Warm','Cold'],[24,35,41])[0],rng.choice(['Summer discovery','Always on','Consultation drive','Return visitors']),str(qualified).lower(),str(converted).lower() if rng.random()>.13 else '',rng.choice(['West','South','North','East']),rng.choices(['English','Hindi','Marathi'],[50,35,15])[0],f'2026-08-{rng.randint(1,28):02}',round(rng.uniform(120,2500),2) if converted else ''])
                profile=ingest_file(path,path.name,root)
                profile['isDemo']=True
                store.save_dataset(profile)
                return public_profile(profile)
        finally:
            upload_gate.release()

    @app.get('/api/datasets/{dataset_id}',operation_id='getDataset')
    def get_dataset(dataset_id:str):
        return public_profile(profile_for(dataset_id))

    @app.get('/api/datasets/{dataset_id}/preview',operation_id='getDatasetPreview')
    def preview(dataset_id:str,offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100)):
        return preview_rows(profile_for(dataset_id),offset,limit)

    @app.get('/api/datasets/{dataset_id}/answers',operation_id='listAnswers')
    def answers(dataset_id:str):
        profile_for(dataset_id)
        return store.answers(dataset_id)

    @app.post('/api/datasets/{dataset_id}/chat',operation_id='answerDatasetQuestion')
    def chat(dataset_id:str,body:ChatRequest):
        if not body.question.strip():
            raise ValueError('Enter a question about your data.')
        p=profile_for(dataset_id)
        if not chat_gate.acquire(blocking=False):
            return error(429,'CHAT_BUSY','Two analyses are already running. Try again shortly.')
        try:
            answer=answer_question(p,body.question,store.answers(dataset_id))
            store.save_answer(dataset_id,answer)
            return answer
        finally:
            chat_gate.release()

    @app.get('/api/datasets/{dataset_id}/pins',operation_id='listPinnedAnswers')
    def pins(dataset_id:str):
        profile_for(dataset_id)
        return store.answers(dataset_id,pinned=True)

    @app.post('/api/datasets/{dataset_id}/pins',operation_id='setAnswerPinned')
    def pin(dataset_id:str,body:PinRequest):
        profile_for(dataset_id)
        store.pin(dataset_id,body.answerId,body.pinned)
        return {'answerId':body.answerId,'pinned':body.pinned}

    @app.get('/api/openapi.yaml',operation_id='getApiSpecification')
    def specification():
        return FileResponse(ROOT/'docs/openapi.yaml',media_type='application/yaml')

    client_dir=ROOT/'dist/client'
    if client_dir.exists():
        app.mount('/',StaticFiles(directory=client_dir,html=True),name='client')
    return app
