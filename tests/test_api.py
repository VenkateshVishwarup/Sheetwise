import importlib
from fastapi.testclient import TestClient
from tests.test_ingest import make_csv


def test_upload_preview_dashboard_and_persistence(tmp_path, monkeypatch):
    main=importlib.import_module('backend.main')
    monkeypatch.delenv('WORKSPACE_PASSWORD', raising=False)
    app=main.create_app(tmp_path/'data', local_mode=True)
    client=TestClient(app)
    with make_csv(tmp_path).open('rb') as file:
        response=client.post('/api/datasets', files={'file':('users.csv',file,'text/csv')})
    assert response.status_code==201, response.text
    dataset=response.json()
    assert 'databasePath' not in dataset
    did=dataset['id']
    assert client.get('/api/datasets').json()[0]['rowCount']==3
    assert client.get(f'/api/datasets/{did}/preview').json()['rows'][0]['c4']=='••••'
    assert len(client.get(f'/api/datasets/{did}').json()['dashboard'])>=2
    assert TestClient(main.create_app(tmp_path/'data', local_mode=True)).get('/api/datasets').json()[0]['id']==did
    assert client.post('/api/datasets', files={'file':('bad.txt',b'hello','text/plain')}).status_code==400
    assert client.get('/api/datasets/not-an-id').status_code==400


def test_password_and_cross_origin_writes(tmp_path, monkeypatch):
    main=importlib.import_module('backend.main')
    monkeypatch.setenv('WORKSPACE_PASSWORD','a-long-test-password')
    app=main.create_app(tmp_path/'data', local_mode=False)
    client=TestClient(app)
    assert client.get('/api/datasets').status_code==401
    assert client.post('/api/session',json={'password':'wrong'}).status_code==401
    response=client.post('/api/session',json={'password':'a-long-test-password'})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/datasets').status_code==200
    assert client.post('/api/demo',headers={'origin':'https://evil.example'}).status_code==403


def test_nonlocal_mode_requires_password(tmp_path, monkeypatch):
    import pytest
    main=importlib.import_module('backend.main')
    monkeypatch.delenv('WORKSPACE_PASSWORD', raising=False)
    with pytest.raises(ValueError, match='WORKSPACE_PASSWORD'):
        main.create_app(tmp_path/'data', local_mode=False)


def test_passwordless_mode_rejects_untrusted_host(tmp_path, monkeypatch):
    main=importlib.import_module('backend.main')
    monkeypatch.delenv('WORKSPACE_PASSWORD', raising=False)
    app=main.create_app(tmp_path/'data',local_mode=True)
    client=TestClient(app,base_url='http://attacker.example',client=('127.0.0.1',1234))
    assert client.get('/api/datasets').status_code==403


def test_chat_pin_and_reload_use_executed_results(tmp_path, monkeypatch):
    from backend import main
    from backend.agent import answer_question
    monkeypatch.delenv('WORKSPACE_PASSWORD', raising=False)
    def provider(stage,payload):
        if stage=='plan':
            return {'columns':[],'plan':'Count records.','clarification':'','choices':[]}
        return {'sql':'SELECT COUNT(*) AS records FROM dataset','title':'Records','chartType':'metric'}
    monkeypatch.setattr(main,'answer_question',lambda p,q,h:answer_question(p,q,h,provider=provider))
    root=tmp_path/'data'
    client=TestClient(main.create_app(root,local_mode=True))
    with make_csv(tmp_path).open('rb') as file:
        did=client.post('/api/datasets',files={'file':('users.csv',file,'text/csv')}).json()['id']
    response=client.post(f'/api/datasets/{did}/chat',json={'question':'How many records?'})
    assert response.status_code==200
    answer=response.json()
    assert answer['result']['rows']==[[3]]
    assert answer['messages'][2]['updateDataModel']['value']['value']==3
    assert client.post(f'/api/datasets/{did}/pins',json={'answerId':answer['id'],'pinned':True}).status_code==200
    reloaded=TestClient(main.create_app(root,local_mode=True))
    assert reloaded.get(f'/api/datasets/{did}/pins').json()[0]['pinned'] is True
    assert reloaded.get(f'/api/datasets/{did}/answers').json()[0]['sql']=='SELECT COUNT(*) AS records FROM dataset'
    assert reloaded.post(f'/api/datasets/{did}/pins',json={'answerId':answer['id'],'pinned':False}).status_code==200
    assert reloaded.get(f'/api/datasets/{did}/pins').json()==[]
