import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { activeIncident, closeOpenIncidents, signIn } from './helpers';

/** Phase 6 exit: closing an incident produces a report with EN + UR PDFs. */
test('commander closes an incident, opens its report and downloads both PDFs', async ({
  page,
  baseURL,
}) => {
  await closeOpenIncidents(baseURL!);
  const inc = await activeIncident(baseURL!, [{ username: 'responder1', zone: 'F1-Z1' }]);
  await signIn(page, 'commander1');
  await page.goto(`/live?incident=${inc.id}`);
  await page.getByTestId('close-incident').click();
  await page.getByTestId('confirm-button').click();
  await expect(page.getByTestId('live-empty')).toBeVisible();

  await page.locator('[data-nav=reports]').click();
  await page.getByTestId('reports-search').fill(inc.code);
  const row = page.locator(`[data-testid=reports-table] tr[data-code="${inc.code}"]`);
  await expect(row).toBeVisible();
  await row.getByRole('link').click();
  await expect(page.getByTestId('report-detail')).toContainText(inc.code);
  await expect(page.getByTestId('report-narrative')).toContainText(inc.code);
  await expect(page.getByTestId('report-timeline')).toContainText('Incident closed');

  for (const lang of ['en', 'ur'] as const) {
    const [dl] = await Promise.all([
      page.waitForEvent('download'),
      page.getByTestId(`pdf-${lang}`).click(),
    ]);
    expect(dl.suggestedFilename()).toBe(`${inc.code}-report-${lang}.pdf`);
    const bytes = readFileSync((await dl.path())!);
    expect(bytes.subarray(0, 5).toString()).toBe('%PDF-');
    expect(bytes.length).toBeGreaterThan(10_000);
  }

  await page.getByTestId('regenerate').click();
  await expect(page.getByText('Report regenerated.')).toBeVisible();
  await page.screenshot({ path: 'test-results/report-en.png', fullPage: true });
});

test('seeded demo report renders in Urdu; admin can delete, responders cannot see reports', async ({
  browser,
}) => {
  const ctx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();
  await signIn(page, 'admin');
  await page.locator('[data-nav=reports]').click();
  const demo = page.locator('[data-testid=reports-table] tr', {
    hasText: 'Gul Plaza, M.A. Jinnah Road (demo)',
  });
  await expect(demo.first()).toBeVisible();
  await demo.first().getByRole('link').click();
  await expect(page.getByTestId('report-detail')).toBeVisible();
  await expect(page.getByTestId('regenerate')).toHaveCount(0); // commander only
  await expect(page.getByTestId('delete-incident')).toBeVisible();
  await page.locator('.shell-header .lang-switch button[lang=ur]').click();
  await expect(page.getByTestId('report-timeline')).toContainText('واقعہ');
  await page.screenshot({ path: 'test-results/report-ur.png', fullPage: true });
  await page.locator('.shell-header .lang-switch button[lang=en]').click();
  // Delete dialog opens and can be cancelled (the demo record stays for other runs).
  await page.getByTestId('delete-incident').click();
  await expect(page.getByRole('dialog')).toContainText('Delete incident');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await ctx.close();

  const rctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const responder = await rctx.newPage();
  await signIn(responder, 'responder1');
  await expect(responder.locator('[data-nav=reports]')).toHaveCount(0);
  await rctx.close();
});
