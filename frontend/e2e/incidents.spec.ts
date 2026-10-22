import { expect, test } from '@playwright/test';
import { closeOpenIncidents, signIn } from './helpers';

/** Phase 3 exit: a commander creates an incident; a second browser sees updates live. */
test('commander dispatches, activates, reassigns and closes; admin sees it all live', async ({
  browser,
  baseURL,
}) => {
  await closeOpenIncidents(baseURL!);
  const cmdCtx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
  });
  const adminCtx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
  });
  const cmd = await cmdCtx.newPage();
  const admin = await adminCtx.newPage();

  await signIn(cmd, 'commander1');
  await signIn(admin, 'admin');
  await expect(cmd.getByTestId('live-empty')).toBeVisible();
  await expect(admin.getByTestId('live-empty')).toBeVisible();
  await expect(admin.getByTestId('open-dispatch')).toHaveCount(0); // read-only

  // 1. Dispatch
  await cmd.getByTestId('open-dispatch').click();
  await cmd.locator('#f-address').fill('Gul Plaza, M.A Jinnah Road');
  await cmd.locator('#f-floors').fill('2');
  await cmd.locator('#f-zpf').fill('4');
  await cmd.getByLabel('F1-Z1 label').fill('Lobby');
  const row = cmd.getByTestId('team-row-0');
  await row.getByLabel('Responder').selectOption({ label: 'Demo Field Responder' });
  await row.getByLabel('Zone', { exact: true }).selectOption('F1-Z2');
  await cmd.getByTestId('dispatch-submit').click();
  await expect(cmd.getByTestId('live-briefing')).toBeVisible();
  await expect(cmd.locator('[data-zone="F1-Z1"]')).toContainText('Lobby');

  // 2. Second browser picks it up without reloading (station channel)
  await expect(admin.getByTestId('live-briefing')).toBeVisible({ timeout: 10_000 });
  await expect(admin.locator('[data-zone="F1-Z2"]')).toContainText('Demo Field Responder');

  // 3. Go live — both switch to the live state
  await cmd.getByTestId('go-live').click();
  await expect(cmd.getByTestId('live-active')).toBeVisible();
  await expect(admin.getByTestId('live-active')).toBeVisible({ timeout: 10_000 });
  await expect(admin.getByTestId('kpi-strip')).toContainText('Unclassified');
  await expect(admin.locator('[data-zone="F1-Z2"]')).toHaveAttribute('data-status', 'unclassified');
  await expect(admin.getByTestId('evac-bar')).toContainText('Not enough analysed zones');
  await cmd.screenshot({ path: 'test-results/live-active-en.png', fullPage: true });

  // 4. Reassign on the team page → admin's live map follows
  await cmd.locator('[data-nav=team]').click();
  const current = cmd.getByTestId('current-assignments');
  await current
    .locator('tr[data-user=responder1]')
    .getByLabel('Move to zone')
    .selectOption({ label: 'F2-Z3' });
  await expect(admin.locator('[data-zone="F2-Z3"]')).toContainText('Demo Field Responder', {
    timeout: 10_000,
  });
  await expect(admin.locator('[data-zone="F1-Z2"]')).not.toContainText('Demo Field Responder');
  await expect(cmd.getByTestId('assignment-history').locator('tbody tr')).toHaveCount(2);

  // 5. Zone drawer + Urdu on the admin side (switching language keeps the page)
  await admin.locator('[data-zone="F2-Z3"]').click();
  await expect(admin.getByTestId('zone-drawer')).toContainText('F2-Z3');
  await admin.locator('.shell-header .lang-switch button[lang=ur]').click();
  await expect(admin.getByTestId('zone-drawer')).toBeVisible();
  await expect(admin.getByTestId('live-active')).toContainText('عمارتی نقشہ');
  await admin.screenshot({ path: 'test-results/live-active-ur.png', fullPage: true });
  await admin.locator('.shell-header .lang-switch button[lang=en]').click();

  // 6. Close with confirmation → both back to empty
  await cmd.locator('[data-nav=live]').click();
  await cmd.getByTestId('close-incident').click();
  await cmd.getByTestId('confirm-button').click();
  await expect(cmd.getByTestId('live-empty')).toBeVisible();
  await expect(admin.getByTestId('live-empty')).toBeVisible({ timeout: 10_000 });

  await cmdCtx.close();
  await adminCtx.close();
});

test('responder sees only their own assignment on the team page', async ({ page, baseURL }) => {
  await closeOpenIncidents(baseURL!);
  await signIn(page, 'responder1');
  await page.locator('[data-nav=team]').click();
  await expect(page.getByText('You are not assigned to an open incident.')).toBeVisible();
});

test.describe('phone (360px)', () => {
  test.use({ viewport: { width: 360, height: 740 }, hasTouch: true, isMobile: true });
  test('dispatch form and live view fit a phone', async ({ page, baseURL }) => {
    await closeOpenIncidents(baseURL!);
    await signIn(page, 'commander1');
    await page.getByTestId('open-dispatch').click();
    await page.locator('#f-address').fill('Phone test');
    await page.getByTestId('dispatch-submit').click();
    await page.getByTestId('go-live').click();
    await expect(page.getByTestId('live-active')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      360,
    );
    await page.screenshot({ path: 'test-results/live-phone.png', fullPage: true });
  });
});
