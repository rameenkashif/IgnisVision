import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, request, test } from '@playwright/test';
import { activeIncident, closeOpenIncidents, signIn } from './helpers';

/**
 * HANDOFF §12 / SRS §5.2.2: the backend restarts cleanly and the browser reconnects its
 * WebSockets and resumes the capture session without signing in again. Restarts the backend
 * container, so it only runs with E2E_DOCKER_RESTART=1 (set in CI).
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

test('backend restart: capture resumes and the dashboard reconnects without signing in', async ({
  browser,
  baseURL,
}) => {
  test.skip(!process.env.E2E_DOCKER_RESTART, 'needs Docker access (E2E_DOCKER_RESTART=1)');
  test.setTimeout(180_000);
  await closeOpenIncidents(baseURL!);
  const inc = await activeIncident(baseURL!, [{ username: 'responder1', zone: 'F1-Z3' }]);

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
  const cmd = await cmdCtx.newPage();
  const phone = await phoneCtx.newPage();
  await signIn(cmd, 'commander1');
  await cmd.goto(`/live?incident=${inc.id}`);
  await expect(cmd.getByTestId('conn-indicator')).toHaveClass(/ok/);
  await signIn(phone, 'responder1');
  await phone.getByTestId('capture-toggle').click();
  const meta = phone.getByTestId('capture-meta');
  await expect(meta).toHaveAttribute('data-state', 'streaming');
  await expect(meta).toContainText('Last result', { timeout: 10_000 });

  execSync('docker compose restart backend', { cwd: ROOT, stdio: 'inherit' });
  const api = await request.newContext({ baseURL, ignoreHTTPSErrors: true });
  await expect
    .poll(async () => (await api.get('/api/v1/health/ready').catch(() => null))?.status(), {
      timeout: 90_000,
    })
    .toBe(200);
  await api.dispose();

  // The phone reconnects by itself and gets fresh results; nobody is sent to sign-in.
  const before = await meta.innerText();
  await expect(meta).toHaveAttribute('data-state', 'streaming', { timeout: 30_000 });
  await expect.poll(() => meta.innerText(), { timeout: 30_000 }).not.toBe(before);
  await expect(phone).toHaveURL(/\/capture$/);
  await expect(cmd.getByTestId('conn-indicator')).toHaveClass(/ok/, { timeout: 30_000 });
  await expect(cmd).toHaveURL(/\/live/);
  await expect(cmd.getByTestId('live-active')).toBeVisible();

  await phone.getByTestId('capture-toggle').click();
  await cmdCtx.close();
  await phoneCtx.close();
});
