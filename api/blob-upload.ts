import { createHash, createHmac, timingSafeEqual } from 'node:crypto';
import { handleUpload, type HandleUploadBody } from '@vercel/blob/client';

export function validSession(cookie: string, password: string, now = Date.now()) {
  if (!password) return false;
  const token = cookie.split(';').map(v => v.trim()).find(v => v.startsWith('sheetwise_session='))?.slice('sheetwise_session='.length);
  if (!token) return false;
  const parts = token.split('.');
  if (parts.length !== 3) return false;
  const [expiry, nonce, signature] = parts;
  if (!/^\d+$/.test(expiry) || !/^[a-f0-9]{32}$/.test(nonce) || !/^[a-f0-9]{64}$/.test(signature) || Number(expiry) * 1000 <= now) return false;
  const secret = createHash('sha256').update('sheetwise-session-v1:' + password).digest();
  const expected = createHmac('sha256', secret).update(`${expiry}.${nonce}`).digest();
  return timingSafeEqual(Buffer.from(signature, 'hex'), expected);
}

export async function POST(request: Request) {
  const failure = (status: number, message: string) => Response.json({ error: { code: 'UPLOAD_REJECTED', message, requestId: crypto.randomUUID() } }, { status });
  if (request.method !== 'POST') return failure(405, 'Use POST for uploads.');
  try {
    const content = await request.text();
    if (content.length > 32768) return failure(413, 'Upload request is too large.');
    const body = JSON.parse(content) as HandleUploadBody;
    const result = await handleUpload({
      request,
      body,
      onBeforeGenerateToken: async pathname => {
        const origin = request.headers.get('origin');
        const host = request.headers.get('host');
        if (origin && new URL(origin).host !== host) throw new Error('Open the workspace to upload.');
        if (!validSession(request.headers.get('cookie') ?? '', process.env.WORKSPACE_PASSWORD ?? '')) throw new Error('Unlock the workspace before uploading.');
        if (!/^uploads\/[a-f0-9-]{36}\.(csv|xlsx)$/.test(pathname)) throw new Error('Choose a CSV or XLSX file.');
        return { maximumSizeInBytes: 100 * 1024 * 1024, allowedContentTypes: ['application/octet-stream'], addRandomSuffix: false, allowOverwrite: false, validUntil: Date.now() + 15 * 60 * 1000 };
      },
      // The SDK authenticates provider callbacks; import runs separately after upload.
      onUploadCompleted: async () => {},
    });
    return Response.json(result, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return failure(400, 'Upload could not be authorized. Unlock the workspace and try again.');
  }
}
