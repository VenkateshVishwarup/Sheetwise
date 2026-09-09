export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...init, headers });
  const data = await response.json().catch(() => null) as { error?: { message?: string } } | null;
  if (!response.ok) throw new Error(data?.error?.message || 'Could not reach the workspace. Check that the app server is running.');
  return data as T;
}
export const number = (value: number) => new Intl.NumberFormat('en', { maximumFractionDigits: 2 }).format(value);
