import asyncio


def test_chunked_upload_is_limited_before_app_is_called():
    from backend.limits import RequestBounds
    called=[]
    sent=[]
    async def app(scope,receive,send):
        called.append(True)
    events=iter([{'type':'http.request','body':b'x'*700,'more_body':True},{'type':'http.request','body':b'x'*700,'more_body':False}])
    async def receive():
        return next(events)
    async def send(message):
        sent.append(message)
    asyncio.run(RequestBounds(app,max_upload_bytes=1024)({'type':'http','method':'POST','path':'/api/datasets','headers':[]},receive,send))
    assert not called
    assert sent[0]['status']==413
