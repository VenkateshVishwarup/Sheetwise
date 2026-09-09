import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash, createHmac } from 'node:crypto';
import { POST, validSession } from '../api/blob-upload';

void test('direct upload auth matches Python sessions and rejects tampering', () => {
  const password='test-workspace-password';
  const now=Date.now();
  const value=`${Math.floor(now/1000)+60}.${'a'.repeat(32)}`;
  const secret=createHash('sha256').update('sheetwise-session-v1:'+password).digest();
  const signature=createHmac('sha256',secret).update(value).digest('hex');
  const cookie=`sheetwise_session=${value}.${signature}`;
  assert.equal(validSession(cookie,password,now),true);
  assert.equal(validSession(cookie,'wrong',now),false);
  assert.equal(validSession(cookie,password,now+120000),false);
  assert.equal(validSession(cookie+'x',password,now),false);
  assert.equal(validSession('',password,now),false);
});

void test('upload entry point accepts a Web Request and rejects malformed JSON', async () => {
  const result=await POST(new Request('https://sheetwise.example/api/blob-upload',{method:'POST',body:'invalid json'}));
  assert.equal(result.status,400);
  assert.match(await result.text(),/UPLOAD_REJECTED/);
});
