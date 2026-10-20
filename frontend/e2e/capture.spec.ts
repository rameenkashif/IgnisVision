import { expect, test } from '@playwright/test';
import { activeIncident, closeOpenIncidents, recordSpeech, signIn } from './helpers';

/**
 * Phase 4 exit (HANDOFF §13/§14 step 4): a responder streams a zone from a phone; the
 * commander's map changes within 6 s; with MOCK_SCENARIO=escalating a rapid change raises a
 * critical alert that is shown and spoken.
 */
test('phone capture drives the commander map; rapid change is alerted and spoken', async ({
  browser,
  baseURL,
}) => {
  test.setTimeout(90_000);
  await closeOpenIncidents(baseURL!);
  const inc = await activeIncident(baseURL!, [{ username: 'responder1', zone: 'F1-Z2' }]);

  const cmdCtx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
  });
  const phoneCtx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    permissions: ['camera'],
  });
  await cmdCtx.addInitScript(recordSpeech);
  await phoneCtx.addInitScript(recordSpeech);
  const cmd = await cmdCtx.newPage();
  const phone = await phoneCtx.newPage();

  await signIn(cmd, 'commander1');
  await cmd.goto(`/live?incident=${inc.id}`);
  await expect(cmd.getByTestId('live-active')).toBeVisible();
  const cell = cmd.locator('[data-zone="F1-Z2"]');
  await expect(cell).toHaveAttribute('data-status', 'unclassified');

  await signIn(phone, 'responder1');
  await expect(phone).toHaveURL(/\/capture$/);
  await expect(phone.getByTestId('capture-zone')).toContainText('★ F1-Z2');
  await expect(phone.getByTestId('cam-indicator')).toBeVisible();

  const t0 = Date.now();
  await phone.getByTestId('capture-toggle').click();
  await expect(phone.getByTestId('cam-indicator')).toContainText('Camera on');
  // Commander's zone leaves "unclassified" within 6 s of streaming starting.
  await expect(cell).not.toHaveAttribute('data-status', 'unclassified', { timeout: 6_000 });
  const firstUpdateMs = Date.now() - t0;
  await expect(phone.getByTestId('capture-reasons').locator('li')).not.toHaveCount(0);
  await expect(cmd.getByTestId('rgb-panel').locator('img').first()).toBeVisible();

  // Escalating storyline: safe → caution → unsafe within ~20 s → critical rapid-change alert.
  await expect(cell).toHaveAttribute('data-status', 'unsafe', { timeout: 40_000 });
  await expect(cmd.getByTestId('topbar')).toHaveClass(/crit/);
  await expect(cmd.getByTestId('alert-feed')).toContainText('changed rapidly');
  await expect(phone.getByTestId('capture-status')).toContainText('Unsafe');
  await expect(phone.getByTestId('capture-spoken')).toContainText('Turn back');
  await expect
    .poll(() =>
      phone.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.join(' | ')),
    )
    .toContain('is now Unsafe. Turn back.');
  await expect
    .poll(() =>
      cmd.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.join(' | ')),
    )
    .toContain('changed rapidly');

  await phone.screenshot({ path: 'test-results/capture-phone.png' });
  await cmd.screenshot({ path: 'test-results/capture-commander.png', fullPage: true });
  await phone.getByTestId('capture-toggle').click();
  await expect(phone.getByTestId('cam-indicator')).toContainText('Camera off');
  console.log(`first zone update after start: ${firstUpdateMs} ms`);

  await cmdCtx.close();
  await phoneCtx.close();
});

test('capture page explains when there is nothing to capture', async ({ page, baseURL }) => {
  await closeOpenIncidents(baseURL!);
  await signIn(page, 'responder1');
  await expect(page.getByTestId('capture-empty')).toBeVisible();
});
