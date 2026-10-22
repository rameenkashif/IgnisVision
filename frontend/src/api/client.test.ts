import { authFetch } from './client';
import { useAuth } from '../stores/auth';

const user = {
  id: 'u1',
  username: 'c1',
  full_name: 'C One',
  role: 'incident_commander',
  preferred_language: 'en',
  is_active: true,
  must_change_password: false,
  onboarding_completed: true,
  station: null,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
} as const;

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
const expired = () =>
  json(401, { error: { code: 'token_expired', message_key: 'errors.token_expired', params: {} } });

describe('authFetch', () => {
  beforeEach(() => useAuth.getState().setSession('old-token', { ...user }, 1800));
  afterEach(() => vi.restoreAllMocks());

  it('attaches the bearer token', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, {}));
    await authFetch(new Request('https://x/api/v1/auth/me'));
    expect((spy.mock.calls[0]![0] as Request).headers.get('authorization')).toBe(
      'Bearer old-token',
    );
  });

  it('refreshes once for concurrent expired requests, then replays them', async () => {
    let refreshes = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith('/auth/refresh')) {
        refreshes++;
        await new Promise((r) => setTimeout(r, 10));
        return json(200, {
          access_token: 'new-token',
          expires_in: 900,
          idle_timeout_s: 1800,
          user,
        });
      }
      return (input as Request).headers.get('authorization') === 'Bearer new-token'
        ? json(200, { ok: 1 })
        : expired();
    });
    const [a, b] = await Promise.all([
      authFetch(new Request('https://x/api/v1/a')),
      authFetch(new Request('https://x/api/v1/b')),
    ]);
    expect(refreshes).toBe(1);
    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(useAuth.getState().accessToken).toBe('new-token');
  });

  it('signs out with the reason when refresh is refused', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = input instanceof Request ? input.url : String(input);
      return url.endsWith('/auth/refresh')
        ? json(401, {
            error: { code: 'idle_timeout', message_key: 'errors.idle_timeout', params: {} },
          })
        : expired();
    });
    const res = await authFetch(new Request('https://x/api/v1/a'));
    expect(res.status).toBe(401);
    expect(useAuth.getState().status).toBe('anonymous');
    expect(useAuth.getState().signedOutReason).toBe('idle_timeout');
  });
});
