import { expect, type Page } from '@playwright/test';

export const PASSWORD = process.env.E2E_PASSWORD ?? 'Demo-pass-1234';

/** Sign in and get through first-run steps (language choice, onboarding) if they appear. */
export async function signIn(page: Page, username: string, lang: 'en' | 'ur' = 'en') {
  await page.addInitScript(() => sessionStorage.setItem('iv.splashSeen', '1'));
  await page.goto('/signin');
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(PASSWORD);
  await page.locator('form button[type=submit]').click();
  await page.waitForURL((u) => !u.pathname.startsWith('/signin'));
  if (page.url().includes('/language')) {
    await page.locator(`.lang-choice[lang=${lang}]`).click();
  }
  if (
    page.url().includes('/onboarding') ||
    (await page.waitForURL(/onboarding/, { timeout: 2000 }).then(
      () => true,
      () => false,
    ))
  ) {
    await expect(page.getByTestId('onboarding')).toBeVisible();
    // Skip / Finish: first button on step 1 is "Skip".
    await page.locator('.walk-actions .pill-btn.ghost').click();
  }
  await expect(page.getByTestId('side-nav')).toBeVisible();
}

export async function navKeys(page: Page): Promise<string[]> {
  return page
    .locator('[data-nav]')
    .evaluateAll((els) => els.map((e) => e.getAttribute('data-nav')!));
}

/** Close every open incident through the API so each test starts from the empty state. */
export async function closeOpenIncidents(baseURL: string) {
  const { request } = await import('@playwright/test');
  const ctx = await request.newContext({ baseURL, ignoreHTTPSErrors: true });
  const login = await ctx.post('/api/v1/auth/login', {
    data: { username: 'commander1', password: PASSWORD },
  });
  const token = (await login.json()).access_token as string;
  const headers = { Authorization: `Bearer ${token}` };
  const list = await ctx.get('/api/v1/incidents?status=dispatched&status=active&limit=200', {
    headers,
  });
  for (const inc of (await list.json()).items as { id: string }[]) {
    await ctx.post(`/api/v1/incidents/${inc.id}/close`, { headers, data: { confirm: true } });
  }
  await ctx.dispose();
}

/** Commander creates + activates an incident through the API; returns {id, code}. */
export async function activeIncident(
  baseURL: string,
  assign: { username: string; zone: string }[] = [],
) {
  const { request } = await import('@playwright/test');
  const ctx = await request.newContext({ baseURL, ignoreHTTPSErrors: true });
  const login = await ctx.post('/api/v1/auth/login', {
    data: { username: 'commander1', password: PASSWORD },
  });
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const responders = (await (await ctx.get('/api/v1/responders', { headers })).json()) as {
    id: string;
    username: string;
  }[];
  const inc = await (
    await ctx.post('/api/v1/incidents', {
      headers,
      data: {
        address: 'Capture test, Mall Road',
        floors: 1,
        zones_per_floor: 3,
        assignments: assign.map((a) => ({
          user_id: responders.find((r) => r.username === a.username)!.id,
          zone_code: a.zone,
        })),
      },
    })
  ).json();
  await ctx.post(`/api/v1/incidents/${inc.id}/activate`, { headers });
  await ctx.dispose();
  return inc as { id: string; code: string };
}

/** Record speechSynthesis output (headless Chromium has no voices) as window.__spoken. */
export const recordSpeech = () => {
  const spoken: string[] = [];
  (window as unknown as { __spoken: string[] }).__spoken = spoken;
  const voices = [
    { lang: 'en-GB', name: 'Test English', default: true, localService: true, voiceURI: 'en' },
    { lang: 'ur-PK', name: 'Test Urdu', default: false, localService: true, voiceURI: 'ur' },
  ];
  // Plain utterance class: Chromium only accepts real SpeechSynthesisVoice objects otherwise.
  (window as unknown as { SpeechSynthesisUtterance: unknown }).SpeechSynthesisUtterance = class {
    lang = '';
    voice: unknown = null;
    rate = 1;
    constructor(public text: string) {}
  };
  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: {
      speaking: false,
      pending: false,
      getVoices: () => voices,
      speak: (u: SpeechSynthesisUtterance) => spoken.push(u.text),
      cancel: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    },
  });
};
