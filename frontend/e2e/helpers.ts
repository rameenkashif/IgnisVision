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
