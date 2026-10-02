import test, { type TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { createHash, createHmac } from 'node:crypto';
import { POST, validSession } from '../api/blob-upload';

const password='test-workspace-password';
const host='sheetwise.example';
const uploadPath='uploads/00000000-0000-4000-8000-000000000000.csv';

function sessionCookie(secretPassword=password, expiresIn=60) {
  const value=`${Math.floor(Date.now()/1000)+expiresIn}.${'a'.repeat(32)}`;
  const secret=createHash('sha256').update('sheetwise-session-v1:'+secretPassword).digest();
  return `sheetwise_session=${value}.${createHmac('sha256',secret).update(value).digest('hex')}`;
}

function tokenRequest(headers:Record<string,string>={}, pathname=uploadPath) {
  const body=JSON.stringify({type:'blob.generate-client-token',payload:{pathname,clientPayload:null,multipart:true}});
  return POST(new Request(`https://${host}/api/blob-upload`,{method:'POST',headers:{'content-type':'application/json',host,origin:`https://${host}`,...headers},body}));
}

// Each test sets its own deployment variables and captures the server log lines.
function deployment(t:TestContext, env:Record<string,string|undefined>) {
  const names=['WORKSPACE_PASSWORD','BLOB_READ_WRITE_TOKEN','VERCEL_BLOB_READ_WRITE_TOKEN'];
  const saved=Object.fromEntries(names.map(name=>[name,process.env[name]]));
  for (const name of names) {
    if (env[name]===undefined) delete process.env[name]; else process.env[name]=env[name];
  }
  t.after(()=>{ for (const name of names) { if (saved[name]===undefined) delete process.env[name]; else process.env[name]=saved[name]; } });
  // Outside Vercel the SDK also warns about its callback URL; keep only this handler's lines.
  const lines:string[]=[];
  const capture=(...args:unknown[])=>{ const line=args.join(' '); if (line.startsWith('[blob-upload]')) lines.push(line); };
  t.mock.method(console,'warn',capture);
  t.mock.method(console,'error',capture);
  return lines;
}

const configured={WORKSPACE_PASSWORD:password,BLOB_READ_WRITE_TOKEN:'vercel_blob_rw_teststore_abcdefghijklmnop'};

async function rejection(response:Response) {
  const body=await response.json() as {error:{code:string;message:string;requestId:string}};
  return {status:response.status,...body.error};
}

void test('direct upload auth matches Python sessions and rejects tampering', () => {
  const now=Date.now();
  const cookie=sessionCookie();
  assert.equal(validSession(cookie,password,now),true);
  assert.equal(validSession(cookie,'wrong',now),false);
  assert.equal(validSession(cookie,password,now+120000),false);
  assert.equal(validSession(cookie+'x',password,now),false);
  assert.equal(validSession('',password,now),false);
});

void test('a signed-in token request receives a client token and logs nothing', async t => {
  const lines=deployment(t,configured);
  const response=await tokenRequest({cookie:sessionCookie()});
  assert.equal(response.status,200);
  assert.match((await response.json() as {clientToken:string}).clientToken,/^vercel_blob_client_teststore_/);
  assert.deepEqual(lines,[]);
});

void test('malformed JSON is a logged bad request', async t => {
  const lines=deployment(t,configured);
  const result=await rejection(await POST(new Request(`https://${host}/api/blob-upload`,{method:'POST',body:'invalid json'})));
  assert.equal(result.status,400);
  assert.equal(result.code,'INVALID_REQUEST');
  assert.equal(lines.length,1);
  assert.match(lines[0],/not valid JSON/);
  assert.match(lines[0],new RegExp(result.requestId));
});

void test('missing Blob storage configuration is reported as unavailable with the variable name logged', async t => {
  const lines=deployment(t,{WORKSPACE_PASSWORD:password,VERCEL_BLOB_READ_WRITE_TOKEN:'vercel_blob_rw_teststore_abcdefghijklmnop'});
  const result=await rejection(await tokenRequest({cookie:sessionCookie()}));
  assert.equal(result.status,503);
  assert.equal(result.code,'SERVICE_UNAVAILABLE');
  assert.equal(lines.length,1);
  assert.match(lines[0],/BLOB_READ_WRITE_TOKEN is not set/);
  assert.match(lines[0],/VERCEL_BLOB_READ_WRITE_TOKEN is set/);
  assert.doesNotMatch(lines[0],/abcdefghijklmnop/);
});

void test('a missing workspace password is reported as unavailable', async t => {
  const lines=deployment(t,{BLOB_READ_WRITE_TOKEN:configured.BLOB_READ_WRITE_TOKEN});
  const result=await rejection(await tokenRequest({cookie:sessionCookie()}));
  assert.equal(result.status,503);
  assert.match(lines[0],/WORKSPACE_PASSWORD is not set/);
});

void test('session failures say whether the cookie was missing, expired or signed with another password', async t => {
  const lines=deployment(t,configured);
  for (const [cookie,reason] of [[undefined,/no workspace session cookie/i],[sessionCookie(password,-60),/expired/],[sessionCookie('another-password'),/signature/]] as const) {
    const result=await rejection(await tokenRequest(cookie?{cookie}:{}));
    assert.equal(result.status,401);
    assert.equal(result.code,'UNAUTHORIZED');
    assert.match(lines.at(-1)??'',reason);
  }
  assert.ok(lines.every(line=>!line.includes(password)));
});

void test('cross-origin token requests are rejected with both hosts logged', async t => {
  const lines=deployment(t,configured);
  const result=await rejection(await tokenRequest({cookie:sessionCookie(),origin:'https://elsewhere.example'}));
  assert.equal(result.status,403);
  assert.equal(result.code,'ORIGIN_REJECTED');
  assert.match(lines[0],/elsewhere\.example/);
  assert.match(lines[0],/sheetwise\.example/);
});

void test('unsupported upload paths are bad requests', async t => {
  const lines=deployment(t,configured);
  const result=await rejection(await tokenRequest({cookie:sessionCookie()},'uploads/report.pdf'));
  assert.equal(result.status,400);
  assert.equal(result.code,'INVALID_REQUEST');
  assert.match(lines[0],/uploads\/report\.pdf/);
});

void test('unexpected SDK failures are internal errors with the SDK message logged', async t => {
  const lines=deployment(t,{WORKSPACE_PASSWORD:password,BLOB_READ_WRITE_TOKEN:'not-a-blob-token'});
  const result=await rejection(await tokenRequest({cookie:sessionCookie()}));
  assert.equal(result.status,500);
  assert.equal(result.code,'INTERNAL_ERROR');
  assert.match(lines[0],/Invalid `token` parameter/);
  assert.doesNotMatch(lines[0],/not-a-blob-token/);
});
