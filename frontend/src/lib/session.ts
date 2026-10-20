import { api, refreshSession, unwrap, type User } from '../api/client';
import { ApiError, toApiError } from '../api/errors';
import i18n, { currentLang, type Lang } from '../i18n';
import { useAuth } from '../stores/auth';
import { homeFor } from './nav';

let bootstrapped: Promise<void> | null = null;

/** On page load: restore the session from the httpOnly refresh cookie, if any. */
export function bootstrapSession(): Promise<void> {
  bootstrapped ??= (async () => {
    const ok = await refreshSession();
    if (!ok && useAuth.getState().status === 'unknown') useAuth.getState().signedOut(null);
    // A silent "no session" on load is not an error worth showing.
    if (useAuth.getState().signedOutReason === 'not_authenticated')
      useAuth.getState().clearReason();
    const user = useAuth.getState().user;
    if (user?.onboarding_completed) await i18n.changeLanguage(user.preferred_language);
  })();
  return bootstrapped;
}

export async function signIn(username: string, password: string): Promise<User> {
  let res: Response;
  try {
    res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    throw new ApiError(0, 'network');
  }
  if (!res.ok) throw await toApiError(res);
  const body = await res.json();
  useAuth.getState().setSession(body.access_token, body.user, body.idle_timeout_s);
  // Returning users get their saved language; first-timers choose on the language screen.
  if (body.user.onboarding_completed) await i18n.changeLanguage(body.user.preferred_language);
  return body.user as User;
}

export async function signOut(reason: string | null = 'signed_out'): Promise<void> {
  try {
    await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'same-origin' });
  } catch {
    /* offline: the local session is still cleared */
  }
  useAuth.getState().signedOut(reason);
}

/** Change language everywhere: UI immediately, profile in the background. */
export async function setLanguage(lang: Lang): Promise<void> {
  await i18n.changeLanguage(lang);
  if (useAuth.getState().status !== 'authenticated') return;
  try {
    const user = await unwrap(api.PATCH('/api/v1/auth/me', { body: { preferred_language: lang } }));
    useAuth.getState().setUser(user);
  } catch {
    /* kept locally; synced next time */
  }
}

export async function completeOnboarding(): Promise<void> {
  const user = await unwrap(
    api.PATCH('/api/v1/auth/me', {
      body: { onboarding_completed: true, preferred_language: currentLang() },
    }),
  );
  useAuth.getState().setUser(user);
}

/** Where to send a signed-in user next (forced steps first). */
export function nextStep(user: User): string {
  if (user.must_change_password) return '/change-password';
  if (!user.onboarding_completed) return '/language';
  return homeFor(user.role);
}
