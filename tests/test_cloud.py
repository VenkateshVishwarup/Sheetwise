from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


class MemoryBlob:
    def __init__(self): self.objects={}
    def put(self,path,body,**options):
        assert options['access']=='private'
        assert path not in self.objects
        self.objects[path]=body
    def get(self,path,**options):
        assert options['access']=='private'
        return SimpleNamespace(content=self.objects[path]) if path in self.objects else None
    def list_objects(self,prefix,**options):
        return SimpleNamespace(blobs=[SimpleNamespace(pathname=p) for p in self.objects if p.startswith(prefix)],has_more=False)
    def upload_file(self,local_path,path,**options): self.put(path,Path(local_path).read_bytes(),**options)
    def download_file(self,path,local_path,**options):
        assert options['access']=='private'
        Path(local_path).write_bytes(self.objects[path])
    def head(self,path): return SimpleNamespace(size=len(self.objects[path]))
    def delete(self,path): self.objects.pop(path,None)


def test_cloud_upload_survives_instance_restart_and_preserves_auth(tmp_path,monkeypatch):
    blob=MemoryBlob()
    monkeypatch.setenv('STORAGE_MODE','blob')
    monkeypatch.setenv('WORKSPACE_PASSWORD','test-workspace-password')
    monkeypatch.setattr('backend.cloud_store.BlobClient',lambda:blob)
    first=create_app(tmp_path/'first',local_mode=False)
    client=TestClient(first)
    assert client.get('/api/datasets').status_code==401
    assert client.post('/api/session',json={'password':'test-workspace-password'}).status_code==200
    assert client.get('/api/status').json()['directUploads'] is True
    dataset_id=str(uuid4())
    pathname=f'uploads/{dataset_id}.csv'
    blob.objects[pathname]=b'user_id,email,status\nu1,a@example.com,Hot\nu2,b@example.com,Cold\n'
    result=client.post('/api/imports',json={'pathname':pathname,'filename':'leads.csv'})
    assert result.status_code==201,result.text
    assert result.json()['rowCount']==2
    assert pathname not in blob.objects
    assert not list((tmp_path/'first').glob('**/*.duckdb'))
    # No instance-local metadata, signing key, or database survives this restart.
    second=create_app(tmp_path/'second',local_mode=False)
    resumed=TestClient(second)
    resumed.cookies.update(client.cookies)
    assert resumed.get('/api/datasets').json()[0]['id']==dataset_id
    preview=resumed.get(f'/api/datasets/{dataset_id}/preview')
    assert preview.status_code==200,preview.text
    assert 'a@example.com' not in preview.text
    assert not list((tmp_path/'second').glob('**/*.duckdb'))
    answer={'id':str(uuid4()),'createdAt':'2026-09-09T12:00:00Z','summary':'Two records'}
    first.state.store.save_answer(dataset_id,answer)
    second.state.store.pin(dataset_id,answer['id'],True)
    assert first.state.store.answers(dataset_id,pinned=True)[0]['id']==answer['id']
    first.state.store.pin(dataset_id,answer['id'],False)
    assert second.state.store.answers(dataset_id,pinned=True)==[]
    assert resumed.post('/api/imports',json={'pathname':pathname,'filename':'leads.csv'}).status_code==201
    for path in ('https://example.com/data.csv','../profiles/private.csv','uploads/not-a-uuid.csv'):
        assert resumed.post('/api/imports',json={'pathname':path,'filename':'leads.csv'}).status_code==400


def test_cloud_requires_password(tmp_path,monkeypatch):
    monkeypatch.setenv('STORAGE_MODE','blob')
    monkeypatch.delenv('WORKSPACE_PASSWORD',raising=False)
    with pytest.raises(ValueError,match='(?i)password'):
        create_app(tmp_path,local_mode=False)


def test_failed_profile_commit_can_retry_and_cleanup_failure_keeps_success(tmp_path,monkeypatch):
    blob=MemoryBlob()
    monkeypatch.setenv('STORAGE_MODE','blob')
    monkeypatch.setenv('WORKSPACE_PASSWORD','test-workspace-password')
    monkeypatch.setattr('backend.cloud_store.BlobClient',lambda:blob)
    app=create_app(tmp_path,local_mode=False)
    client=TestClient(app)
    client.post('/api/session',json={'password':'test-workspace-password'})
    pathname=f'uploads/{uuid4()}.csv'
    blob.objects[pathname]=b'status\nHot\nCold\n'
    original=blob.put
    def fail_profile(path,body,**options):
        if path.startswith('profiles/'):
            raise RuntimeError('Temporary storage outage')
        return original(path,body,**options)
    blob.put=fail_profile
    body={'pathname':pathname,'filename':'leads.csv'}
    assert client.post('/api/imports',json=body).status_code==503
    assert pathname in blob.objects
    blob.put=original
    def fail_cleanup(path): raise RuntimeError('Temporary cleanup outage')
    blob.delete=fail_cleanup
    response=client.post('/api/imports',json=body)
    assert response.status_code==201,response.text
    assert response.json()['rowCount']==2
    assert client.get('/api/datasets').json()[0]['id']==response.json()['id']
    assert client.post('/api/imports',json=body).status_code==201
