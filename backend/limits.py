"""Bound request bytes and import concurrency before multipart parsing begins."""
import asyncio
import tempfile
from starlette.responses import JSONResponse


class RequestBounds:
    def __init__(self, app, max_upload_bytes=101*1024*1024):
        self.app=app
        self.max_upload_bytes=max_upload_bytes
        self.import_active=False

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method') not in ('POST','PUT','PATCH') or not scope.get('path','').startswith('/api/'):
            return await self.app(scope,receive,send)
        upload=scope['path']=='/api/datasets'
        limit=self.max_upload_bytes if upload else 32*1024
        async def reject(status,code,message):
            await JSONResponse({'error':{'code':code,'message':message,'requestId':'request-limit'}},status_code=status)(scope,receive,send)
        if upload and self.import_active:
            return await reject(429,'IMPORT_BUSY','Another upload is in progress. Try again shortly.')
        if upload:
            self.import_active=True
        try:
            # A bounded spool also covers chunked requests without Content-Length.
            with tempfile.SpooledTemporaryFile(max_size=1024*1024) as spool:
                total=0
                while True:
                    event=await receive()
                    if event['type']=='http.disconnect':
                        return
                    chunk=event.get('body',b'')
                    total+=len(chunk)
                    if total>limit:
                        return await reject(413,'FILE_TOO_LARGE','The request exceeds the allowed size.')
                    spool.write(chunk)
                    if not event.get('more_body',False):
                        break
                spool.seek(0)
                exhausted=False
                async def replay():
                    nonlocal exhausted
                    if exhausted:
                        return await receive()
                    chunk=spool.read(65536)
                    exhausted=spool.tell()>=total
                    return {'type':'http.request','body':chunk,'more_body':not exhausted}
                await self.app(scope,replay,send)
        finally:
            if upload:
                self.import_active=False
