import { expect, request, test } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeIncident, closeOpenIncidents, PASSWORD, signIn } from './helpers';

const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');

/** Phase 5 exit (HANDOFF §14 steps 5–6): uploading a video produces a ranked victim list on
 * the dashboard; a mobile sync payload adds victims from source "mobile" (posted twice →
 * created once). */
test('thermal video → ranked victims; mobile sync adds mobile victims once', async ({
  page,
  baseURL,
}) => {
  test.setTimeout(90_000);
  await closeOpenIncidents(baseURL!);
  const inc = await activeIncident(baseURL!, [{ username: 'responder1', zone: 'F1-Z1' }]);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, 'commander1');

  // Upload on the analysis page, tagged to a zone
  await page.locator('[data-nav=analysis]').click();
  const z1 = inc.zones.find((z) => z.code === 'F1-Z1')!;
  await page.getByTestId('analysis-zone').selectOption(z1.id);
  await page.getByTestId('analysis-file').setInputFiles(path.join(FIXTURES, 'thermal.mp4'));
  await page.getByTestId('analysis-upload').click();
  const row = page.getByTestId('upload-list').locator('.upload-item').first();
  await expect(row).toHaveAttribute('data-job-status', 'done', { timeout: 30_000 });
  await expect(page.getByTestId('detection-viewer').locator('rect')).toHaveCount(2, {
    timeout: 10_000,
  });
  await page.screenshot({ path: 'test-results/analysis-video.png', fullPage: true });

  // Dashboard: ranked list, critical first, KPI and thermal panel
  await page.goto(`/live?incident=${inc.id}`);
  const list = page.getByTestId('victim-list');
  await expect(list.locator('li')).toHaveCount(2);
  await expect(list.locator('li').first()).toHaveAttribute('data-band', 'critical');
  await expect(list.locator('li').first()).toContainText('Lying');
  await expect(page.getByTestId('kpi-strip')).toContainText('2');
  await expect(page.getByTestId('thermal-panel').locator('img')).toBeVisible();
  await expect(page.getByTestId('thermal-panel').locator('rect')).toHaveCount(2);
  await expect(page.getByTestId('alert-feed')).toContainText('Critical-priority person detected');

  // Mobile sync (the Flutter app's contract), posted twice → one set of victims
  const api = await request.newContext({ baseURL, ignoreHTTPSErrors: true });
  const token = (
    await (
      await api.post('/api/v1/auth/login', { data: { username: 'responder1', password: PASSWORD } })
    ).json()
  ).access_token;
  const body = {
    device_id: 'android-e2e',
    app_version: '1.0.0',
    incidents: [
      {
        client_uuid: `e2e-${Date.now()}`,
        started_at: new Date().toISOString(),
        linked_incident_id: inc.id,
        detections: [
          {
            client_detection_uuid: `e2e-det-${Date.now()}`,
            captured_at: new Date().toISOString(),
            track_id: 1,
            bbox: [0.1, 0.2, 0.3, 0.8],
            posture: 'sitting',
            posture_confidence: 0.8,
            detection_confidence: 0.9,
            rpi_score: 0.5,
            rpi_band: 'medium',
          },
        ],
      },
    ],
  };
  const headers = { Authorization: `Bearer ${token}` };
  const first = await (await api.post('/api/v1/sync/incidents', { data: body, headers })).json();
  const second = await (await api.post('/api/v1/sync/incidents', { data: body, headers })).json();
  expect(first.results[0].status).toBe('created');
  expect(second.results[0].status).toBe('duplicate');
  await api.dispose();

  await expect(list.locator('li')).toHaveCount(3, { timeout: 10_000 });
  await expect(list).toContainText('Mobile');

  // Commander marks the top person rescued → moves below the active ones
  await list.locator('li').first().getByRole('button', { name: 'Mark rescued' }).click();
  await expect(list.locator('li').last()).toHaveAttribute('data-status', 'rescued');
  await page.screenshot({ path: 'test-results/live-victims.png', fullPage: true });
});

test.describe('phone (390px)', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  test('responder uploads a thermal image and sees the detections', async ({ page, baseURL }) => {
    await closeOpenIncidents(baseURL!);
    await activeIncident(baseURL!, [{ username: 'responder1', zone: 'F1-Z2' }]);
    await signIn(page, 'responder1');
    await page.goto('/analysis');
    await page.getByTestId('analysis-file').setInputFiles(path.join(FIXTURES, 'thermal.png'));
    await page.getByTestId('analysis-upload').click();
    await expect(page.locator('.upload-item').first()).toHaveAttribute('data-job-status', 'done', {
      timeout: 20_000,
    });
    await expect(page.getByTestId('detection-viewer')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      390,
    );
    await page.screenshot({ path: 'test-results/analysis-phone.png', fullPage: true });
  });
});
