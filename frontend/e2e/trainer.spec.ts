import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';
import { PASSWORD, signIn } from './helpers';

const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');
const ZONE = 'Zone status: corridor after a fire (PLACEHOLDER)';

/** Label every target of the current item with `label` (the picker advances by itself). */
async function labelAll(page: Page, label: string) {
  const n = await page.getByTestId('target-chip').count();
  await page.getByTestId('target-chip').first().click();
  for (let i = 0; i < n; i++) await page.locator(`.label-picker [data-label=${label}]`).click();
}

/** Phase 7 exit: a trainee completes a scenario and sees the comparison; staff see all results. */
test('trainee completes a scenario, sees the comparison; training staff see the attempt', async ({
  browser,
}) => {
  const tctx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
  });
  const page = await tctx.newPage();
  await signIn(page, 'trainee1');
  await expect(page).toHaveURL(/\/trainer$/);
  await expect(page.locator('.scenario-card')).toHaveCount(3);
  await page
    .locator(`.scenario-card[data-scenario="${ZONE}"]`)
    .getByTestId('open-scenario')
    .click();
  await expect(page.getByTestId('scenario-intro')).toContainText('placeholder');
  await page.getByTestId('start-attempt').click();

  // Item 1: 4 regions; tapping a region on the image selects it too.
  await expect(page.getByTestId('attempt')).toHaveAttribute('data-item-type', 'zone');
  await expect(page.getByTestId('target-chip')).toHaveCount(4);
  await page.locator('.stage-svg [data-target=r2]').click();
  await expect(page.locator('[data-testid=target-chip][data-target=r2]')).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await labelAll(page, 'safe');
  await expect(page.getByTestId('submit-attempt')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/trainer-attempt.png', fullPage: true });
  await page.getByTestId('next-item').click();
  await expect(page.getByTestId('target-chip')).toHaveCount(3);
  await expect(page.getByTestId('submit-attempt')).toBeDisabled();
  await labelAll(page, 'safe');
  await page.getByTestId('submit-attempt').click();

  // Result: 2 of 7 right (one "safe" region per item), with truth + model shown.
  await expect(page.getByTestId('attempt-result')).toBeVisible();
  await expect(page.getByTestId('score')).toHaveText('29%');
  await expect(page.getByTestId('attempt-result')).toContainText('2 / 7');
  const first = page.getByTestId('result-item').first();
  await expect(first.locator('tr[data-correct=true]')).toHaveCount(1);
  await expect(first).toContainText('PLACEHOLDER');
  await first.locator('[data-view=truth]').click();
  await expect(first.locator('.stage-label').nth(3)).toContainText('Blocked');
  await first.locator('[data-view=model]').click();
  await expect(first).toContainText('What the model saw');
  await page.screenshot({ path: 'test-results/trainer-result.png', fullPage: true });
  await page.locator('.shell-header .lang-switch button[lang=ur]').click();
  await expect(page.getByTestId('attempt-result')).toContainText('درست اہداف');
  await page.screenshot({ path: 'test-results/trainer-result-ur.png', fullPage: true });
  await page.locator('.shell-header .lang-switch button[lang=en]').click();
  await expect(page.getByTestId('retry')).toBeVisible();
  const attemptUrl = page.url();

  await tctx.close();

  // Training staff see the attempt in the results view.
  const sctx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
  });
  const staff = await sctx.newPage();
  await signIn(staff, 'trainer1');
  await staff.locator('[data-nav=trainerResults]').click();
  await expect(
    staff.getByTestId('trainee-summary').locator('tr[data-user=trainee1]'),
  ).toBeVisible();
  await staff.getByTestId('trainee-summary').locator('tr[data-user=trainee1] button').click();
  await expect(staff.getByTestId('progress-chart')).toBeVisible();
  await staff.screenshot({ path: 'test-results/trainer-results.png', fullPage: true });
  await staff.goto(attemptUrl);
  await expect(staff.getByTestId('score')).toHaveText('29%');
  await expect(staff.getByTestId('retry')).toHaveCount(0);
  await sctx.close();
});

test('trainee API: incidents are forbidden', async ({ request }) => {
  const login = await request.post('/api/v1/auth/login', {
    data: { username: 'trainee1', password: PASSWORD },
  });
  const token = (await login.json()).access_token as string;
  const r = await request.get('/api/v1/incidents', {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.status()).toBe(403);
});

test('admin labels a new scenario in the browser', async ({ page }) => {
  await signIn(page, 'admin');
  await page.locator('[data-nav=admin]').click();
  await page.getByRole('link', { name: 'Training scenarios' }).click();
  await expect(page).toHaveURL(/\/admin\/scenarios$/);
  await expect(page.getByTestId('admin-scenarios')).toContainText('PLACEHOLDER');
  await page.getByTestId('new-scenario').click();
  const title = `E2E stairwell ${Date.now()}`;
  await page.locator('#sc-title-en').fill(title);
  await page.locator('#sc-title-ur').fill('سیڑھیاں');
  await page.getByTestId('create-scenario').click();
  await expect(page.getByTestId('scenario-editor')).toContainText(title);

  await page
    .getByTestId('add-item')
    .locator('input[type=file]')
    .setInputFiles(path.join(FIXTURES, 'thermal.png'));
  await expect(page.getByTestId('labeller')).toBeVisible();
  await expect(page.getByTestId('item-usable')).toContainText('Not ready');
  await page.getByTestId('apply-grid').click();
  await expect(page.getByTestId('target-list').locator('li')).toHaveCount(4);
  await page.getByTestId('target-list').locator('select').nth(3).selectOption('blocked');
  // Draw one more region as a polygon.
  await page.getByTestId('tool-polygon').click();
  await page.getByTestId('label-stage').scrollIntoViewIfNeeded();
  const box = (await page.getByTestId('label-stage').locator('svg').boundingBox())!;
  for (const [x, y] of [
    [0.1, 0.1],
    [0.3, 0.1],
    [0.3, 0.3],
  ]) {
    await page.mouse.click(box.x + x * box.width, box.y + y * box.height);
  }
  await page.getByTestId('finish-polygon').click();
  await expect(page.getByTestId('target-list').locator('li')).toHaveCount(5);
  await page.getByTestId('save-item').click();
  await expect(page.getByTestId('item-usable')).toContainText('Ready');
  await page.screenshot({ path: 'test-results/admin-labeller.png', fullPage: true });

  await page.getByTestId('delete-scenario').click();
  await page.getByTestId('confirm-button').click();
  await expect(page).toHaveURL(/\/admin\/scenarios$/);
  await expect(page.getByTestId('admin-scenarios')).not.toContainText(title);
});
