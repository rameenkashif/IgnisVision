import createClient from 'openapi-fetch';
import type { components, paths } from './schema';
import { ApiError, toApiError } from './errors';
import { useAuth } from '../stores/auth';

export type User = components['schemas']['UserOut'];
export type TokenOut = components['schemas']['TokenOut'];

const RETRY_ON = new Set(['token_expired', 'invalid_token']);

let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  for (let attempt = 0; attempt < 2; attempt++) {
    let res: Response;
    try {
      res = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'same-origin' });
    } catch {
      return false; // offline: keep the user signed in locally; requests will surface 'network'
    }
    if (res.ok) {
      const body = (await res.json()) as TokenOut;
      useAuth.getState().setSession(body.access_token, body.user, body.idle_timeout_s);
      return true;
    }
    const err = await toApiError(res);
    if (err.code === 'refresh_race' && attempt === 0) {
      await new Promise((r) => setTimeout(r, 250));
      continue;
    }
    useAuth.getState().signedOut(err.code);
    return false;
  }
  return false;
}

/**
 * One refresh at a time — per tab (shared promise) and across tabs (Web Locks), so the
 * rotating refresh cookie is never presented twice.
 */
export function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    const run = () => doRefresh();
    const locked =
      typeof navigator !== 'undefined' && 'locks' in navigator
        ? navigator.locks.request('iv-refresh', run)
        : run();
    refreshing = Promise.resolve(locked).finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

function withAuth(req: Request): Request {
  const token = useAuth.getState().accessToken;
  const headers = new Headers(req.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return new Request(req, { headers, credentials: 'same-origin' });
}

/** fetch with bearer token; on an expired token, refresh once and replay the request. */
export async function authFetch(input: Request): Promise<Response> {
  const replay = input.clone();
  let res: Response;
  try {
    res = await fetch(withAuth(input));
  } catch {
    throw new ApiError(0, 'network');
  }
  if (res.status === 401 && useAuth.getState().accessToken) {
    const err = await toApiError(res);
    if (RETRY_ON.has(err.code) && (await refreshSession())) {
      return fetch(withAuth(replay));
    }
  }
  return res;
}

export const api = createClient<paths>({ baseUrl: '', fetch: authFetch });

/** Unwrap an openapi-fetch result, throwing ApiError on failure. */
export async function unwrap<T>(
  p: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, response } = await p;
  if (!response.ok) throw await toApiError(response);
  return data as T;
}
