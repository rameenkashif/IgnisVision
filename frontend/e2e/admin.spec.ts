import { expect, test } from '@playwright/test';
import { signIn } from './helpers';

test.describe.configure({ mode: 'serial' });

test('admin manages a user end to end; every step is in the audit log', async ({
  page,
  browser,
}) => {
  await signIn(page, 'admin');
  await page.locator('[data-nav=admin]').click();
  await expect(page).toHaveURL(/\/admin\/users$/);
  const username = `e2e.${Date.now()}`;

  // Create → temporary password shown once
  await page.getByTestId('new-user').click();
  await page.locator('#u-username').fill(username);
  await page.locator('#u-fullname').fill('E2E Responder');
  await page.locator('#u-role').selectOption('field_responder');
  await page.getByTestId('save-user').click();
  const temp = (await page.getByTestId('temp-password').textContent())!.trim();
  expect(temp.length).toBeGreaterThanOrEqual(10);
  await page.getByTestId('close-secret').click();

  // The new user must change the temporary password at first sign-in.
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const p2 = await ctx.newPage();
  await p2.addInitScript(() => sessionStorage.setItem('iv.splashSeen', '1'));
  await p2.goto('/signin');
  await p2.locator('#username').fill(username);
  await p2.locator('#password').fill(temp);
  await p2.locator('form button[type=submit]').click();
  await expect(p2).toHaveURL(/change-password/);
  await ctx.close();

  // Edit role, reset password, deactivate, reactivate
  await page.getByTestId('user-search').fill(username);
  const row = page.locator(`[data-testid=users-table] tr[data-user="${username}"]`);
  await expect(row).toContainText('Field Responder');
  await row.locator('[data-action=edit]').click();
  await page.locator('#u-role').selectOption('trainee');
  await page.getByTestId('save-user').click();
  await expect(row).toContainText('Trainee');
  await row.locator('[data-action=reset]').click();
  await page.getByTestId('confirm-button').click();
  await expect(page.getByTestId('temp-password')).not.toHaveText(temp);
  await page.getByTestId('close-secret').click();
  await row.locator('[data-action=deactivate]').click();
  await page.getByTestId('confirm-button').click();
  await expect(row).toContainText('Deactivated');
  await row.locator('[data-action=reactivate]').click();
  await expect(row).toContainText('Active');
  await page.screenshot({ path: 'test-results/admin-users.png', fullPage: true });

  // Audit log shows the deactivation with before/after
  await page.getByRole('link', { name: 'Audit log' }).click();
  await page.getByTestId('audit-action').selectOption('user.deactivate');
  const entry = page.locator('[data-testid=audit-table] tr[data-action="user.deactivate"]').first();
  await expect(entry).toContainText('System Administrator');
  await entry.getByTestId('audit-details').click();
  await expect(page.locator('.table.diff tr.changed')).toContainText('is_active');
  await page.screenshot({ path: 'test-results/admin-audit.png', fullPage: true });
});

test('settings are validated before saving; status shows every component', async ({ page }) => {
  await signIn(page, 'admin');
  await page.goto('/admin/settings');
  const timing = page.locator('[data-section=timing]');
  const evac = timing.locator('[data-field=evacuation_threshold_pct]');
  await evac.fill('150');
  await expect(timing).toContainText('Must be between 0 and 100');
  await expect(page.getByTestId('save-timing')).toBeDisabled();
  await evac.fill('45');
  await page.getByTestId('save-timing').click();
  await expect(timing.getByRole('status')).toHaveText('Saved.');
  const rpi = page.locator('[data-section=rpi]');
  await rpi.locator('[data-field="rpi.bands.high"]').fill('0.9');
  await expect(rpi).toContainText('critical > high > medium');
  await expect(page.getByTestId('save-rpi')).toBeDisabled();
  await page.screenshot({ path: 'test-results/admin-settings.png', fullPage: true });
  await evac.fill('40'); // restore the default for other tests
  await page.getByTestId('save-timing').click();
  await expect(timing.getByRole('status')).toHaveText('Saved.');

  await page.getByRole('link', { name: 'System status' }).click();
  await expect(page.getByTestId('status-overall')).toBeVisible();
  for (const card of ['app', 'db', 'ml', 'jobs', 'storage', 'backups', 'llm', 'users'])
    await expect(page.locator(`[data-card=${card}]`)).toBeVisible();
  await expect(page.locator('[data-card=ml]')).toContainText('Mock models');
  await page.screenshot({ path: 'test-results/admin-status.png', fullPage: true });
});

test('help: ? opens the screen topic in both languages; search filters topics', async ({
  page,
}) => {
  await signIn(page, 'commander1');
  await page.locator('[data-nav=team]').click();
  await page.getByTestId('help-button').click();
  await expect(page).toHaveURL(/\/help\/team$/);
  await expect(
    page.getByTestId('help-team').getByRole('heading', { name: 'History' }),
  ).toBeVisible();
  await page.locator('.shell-header .lang-switch button[lang=ur]').click();
  await expect(page.getByTestId('help-team').getByRole('heading', { name: 'تاریخ' })).toBeVisible();
  await page.screenshot({ path: 'test-results/help-ur.png', fullPage: true });
  await page.locator('.shell-header .lang-switch button[lang=en]').click();
  await page.goto('/help');
  await page.getByTestId('help-search').fill('backup');
  await expect(page.locator('[data-testid=help-index] [data-topic]')).toHaveCount(1);
  await expect(page.locator('[data-topic=admin]')).toBeVisible();
});
