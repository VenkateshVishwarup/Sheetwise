from fastapi.testclient import TestClient
from backend.main import create_app
from tests.test_evaluation import fixture_profile,definition
from tests.test_cloud import MemoryBlob


def test_authenticated_evaluate_and_reload(tmp_path,monkeypatch):
    monkeypatch.setenv('WORKSPACE_PASSWORD','test-password')
    app=create_app(tmp_path/'data',local_mode=False)
    p=fixture_profile(tmp_path);app.state.store.save_dataset(p)
    client=TestClient(app);base=f'/api/datasets/{p["id"]}'
    assert client.post(base+'/readiness',json=definition()).status_code==401
    client.post('/api/session',json={'password':'test-password'})
    r=client.post(base+'/readiness',json=definition())
    assert r.status_code==200 and not r.json()['ready']
    assert client.post(base+'/evaluations',json=definition()).status_code==400
    good=definition(categoriesReviewed=True)
    r=client.post(base+'/evaluations',json=good)
    assert r.status_code==201,r.text
    assert 'databasePath' not in r.text and 'private@example.com' not in r.text
    again=TestClient(create_app(tmp_path/'data',local_mode=False));again.cookies.update(client.cookies)
    assert again.get(base+'/evaluations').json()[0]['id']==r.json()['id']
    assert client.post(base+'/evaluations',json={**good,'featureKeys':['c2']}).status_code==400
    assert client.post(base+'/readiness',json=good,headers={'origin':'https://untrusted.example'}).status_code==403


def test_cloud_evaluation_history_is_private_and_immutable(tmp_path):
    from backend.cloud_store import CloudStore
    blob=MemoryBlob();store=CloudStore(tmp_path,client=blob)
    run={'id':'example','createdAt':'2026-09-21T12:00:00+00:00','definition':definition()}
    store.save_evaluation('dataset',run)
    assert CloudStore(tmp_path/'other',client=blob).evaluations('dataset')==[run]
    assert store.evaluations('different')==[]


def test_cloud_evaluation_materializes_then_removes_database(tmp_path,monkeypatch):
    blob=MemoryBlob()
    monkeypatch.setenv('STORAGE_MODE','blob')
    monkeypatch.setenv('WORKSPACE_PASSWORD','test-password')
    monkeypatch.setattr('backend.cloud_store.BlobClient',lambda:blob)
    app=create_app(tmp_path/'cloud',local_mode=False)
    p=fixture_profile(tmp_path)
    app.state.store.save_dataset(p)
    client=TestClient(app);client.post('/api/session',json={'password':'test-password'})
    response=client.post(f'/api/datasets/{p["id"]}/evaluations',json=definition(categoriesReviewed=True))
    assert response.status_code==201,response.text
    assert not list((tmp_path/'cloud').rglob('*.duckdb'))
    assert client.get(f'/api/datasets/{p["id"]}/evaluations').json()[0]['id']==response.json()['id']
