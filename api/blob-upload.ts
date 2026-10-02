import { createHash, createHmac, timingSafeEqual } from 'node:crypto';
import { handleUpload, type HandleUploadBody } from '@vercel/blob/client';

const NOT_CONFIGURED = 'Uploads are not configured on this server. Ask the workspace administrator to connect private Blob storage.';

// The client SDK discards error bodies, so every rejection is also written to the function log.
// Reasons and context name the failed check; they never contain cookies, passwords or tokens.
class UploadRejection extends Error {
  constructor(readonly status: number, readonly code: string, readonly publicMessage: string, readonly reason: string, readonly context: Record<string, unknown> = {}) {
    super(reason);
  }
}

export function sessionProblem(cookie: string, password: string, now = Date.now()) {
  const token = cookie.split(';').map(v => v.trim()).find(v => v.startsWith('sheetwise_session='))?.slice('sheetwise_session='.length);
  if (!token) return 'No workspace session cookie was sent.';
  const parts = token.split('.');
  if (parts.length !== 3) return 'The workspace session cookie is malformed.';
  const [expiry, nonce, signature] = parts;
  if (!/^\d+$/.test(expiry) || !/^[a-f0-9]{32}$/.test(nonce) || !/^[a-f0-9]{64}$/.test(signature)) return 'The workspace session cookie is malformed.';
  if (Number(expiry) * 1000 <= now) return 'The workspace session cookie has expired.';
  const secret = createHash('sha256').update('sheetwise-session-v1:' + password).digest();
  const expected = createHmac('sha256', secret).update(`${expiry}.${nonce}`).digest();
  if (!timingSafeEqual(Buffer.from(signature, 'hex'), expected)) return 'The workspace session signature does not match this deployment\'s WORKSPACE_PASSWORD.';
  return null;
}

export function validSession(cookie: string, password: string, now = Date.now()) {
  return !!password && sessionProblem(cookie, password, now) === null;
}

function failure(rejection: UploadRejection, event: unknown) {
  const requestId = crypto.randomUUID();
  const entry = { requestId, status: rejection.status, code: rejection.code, event: typeof event === 'string' ? event.slice(0, 60) : null, reason: rejection.reason, ...rejection.context };
  (rejection.status >= 500 ? console.error : console.warn)('[blob-upload]', JSON.stringify(entry));
  return Response.json({ error: { code: rejection.code, message: rejection.publicMessage, requestId } }, { status: rejection.status, headers: { 'Cache-Control': 'no-store' } });
}

export async function POST(request: Request) {
  if (request.method !== 'POST') return failure(new UploadRejection(405, 'INVALID_REQUEST', 'Use POST for uploads.', `Unsupported method ${request.method}.`), null);
  let body: HandleUploadBody;
  try {
    const content = await request.text();
    if (content.length > 32768) return failure(new UploadRejection(413, 'FILE_TOO_LARGE', 'Upload request is too large.', `Request body has ${content.length} characters; the limit is 32768.`), null);
    body = JSON.parse(content) as HandleUploadBody;
  } catch {
    return failure(new UploadRejection(400, 'INVALID_REQUEST', 'Send a valid upload request.', 'Request body is not valid JSON.'), null);
  }
  try {
    // handleUpload needs this token for every event type, so check it before the SDK throws a generic error.
    if (!process.env.BLOB_READ_WRITE_TOKEN?.trim()) {
      const hint = process.env.VERCEL_BLOB_READ_WRITE_TOKEN ? ' VERCEL_BLOB_READ_WRITE_TOKEN is set, but the Blob client SDK only reads BLOB_READ_WRITE_TOKEN.' : '';
      throw new UploadRejection(503, 'SERVICE_UNAVAILABLE', NOT_CONFIGURED, 'BLOB_READ_WRITE_TOKEN is not set for this deployment.' + hint);
    }
    const result = await handleUpload({
      request,
      body,
      onBeforeGenerateToken: async pathname => {
        const origin = request.headers.get('origin');
        const host = request.headers.get('host');
        if (origin && new URL(origin).host !== host) throw new UploadRejection(403, 'ORIGIN_REJECTED', 'Open the workspace to upload.', 'Request origin does not match the host.', { origin, host });
        const password = process.env.WORKSPACE_PASSWORD ?? '';
        if (!password) throw new UploadRejection(503, 'SERVICE_UNAVAILABLE', NOT_CONFIGURED, 'WORKSPACE_PASSWORD is not set for this deployment.');
        const problem = sessionProblem(request.headers.get('cookie') ?? '', password);
        if (problem) throw new UploadRejection(401, 'UNAUTHORIZED', 'Unlock the workspace before uploading.', problem);
        if (!/^uploads\/[a-f0-9-]{36}\.(csv|xlsx)$/.test(pathname)) throw new UploadRejection(400, 'INVALID_REQUEST', 'Choose a CSV or XLSX file.', 'Upload path is not uploads/<uuid>.csv or .xlsx.', { pathname: String(pathname).slice(0, 200) });
        return { maximumSizeInBytes: 100 * 1024 * 1024, allowedContentTypes: ['application/octet-stream'], addRandomSuffix: false, allowOverwrite: false, validUntil: Date.now() + 15 * 60 * 1000 };
      },
      // The SDK authenticates provider callbacks; import runs separately after upload.
      onUploadCompleted: async () => {},
    });
    return Response.json(result, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    const rejection = error instanceof UploadRejection ? error
      : new UploadRejection(500, 'INTERNAL_ERROR', 'Upload could not be authorized. Please try again.', error instanceof Error ? `${error.name}: ${error.message}` : 'Unknown upload authorization error.');
    return failure(rejection, body.type);
  }
}
