import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, request, test, type Browser, type Page } from '@playwright/test';
import { closeOpenIncidents, PASSWORD, recordSpeech, signIn } from './helpers';

/**
 * HANDOFF §14, the definition of done, as one end-to-end run with mock models
 * (human-readable version: docs/DEMO.md). Needs MOCK_SCENARIO=escalating on the backend.
 */
const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');
const stamp = Date.now().toString(36);
const NEW_PASSWORD = `Demo-${stamp}-2026`;

async function context(browser: Browser, phone = false) {
  const ctx = await browser.newContext({
    ignoreHTTPSErrors: true,
    viewport: phone ? { width: 390, height: 844 } : { width: 1440, height: 900 },
    ...(phone ? { isMobile: true, hasTouch: true, permissions: ['camera'] } : {}),
  });
  await ctx.addInitScript(recordSpeech);
  return ctx;
}

async function createUser(page: Page, username: string, fullName: string, role: string) {
  await page.getByTestId('new-user').click();
  await page.locator('#u-username').fill(username);
  await page.locator('#u-fullname').fill(fullName);
  await page.locator('#u-role').selectOption(role);
  await page.getByTestId('save-user').click();
  const temp = (await page.getByTestId('temp-password').textContent())!.trim();
  await page.getByTestId('close-secret').click();
  return temp;
}

test('§14 demo: admin → dispatch → capture → thermal → sync → report → trainer → status', async ({
  browser,
  baseURL,
}) => {
  test.setTimeout(300_000);
  await closeOpenIncidents(baseURL!);

  // 2. Admin creates a commander and two responders; Urdu switches the UI to right-to-left.
  const adminCtx = await context(browser);
  const admin = await adminCtx.newPage();
  await signIn(admin, 'admin');
  await admin.goto('/admin/users');
  const cmdUser = `demo.cmd.${stamp}`;
  const respA = { username: `demo.ra.${stamp}`, name: `Responder A ${stamp}` };
  const respB = { username: `demo.rb.${stamp}`, name: `Responder B ${stamp}` };
  const cmdTemp = await createUser(admin, cmdUser, `Commander ${stamp}`, 'incident_commander');
  const aTemp = await createUser(admin, respA.username, respA.name, 'field_responder');
  await createUser(admin, respB.username, respB.name, 'field_responder');
  await admin.locator('.shell-header .lang-switch button[lang=ur]').click();
  await expect(admin.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(admin.getByRole('link', { name: 'صارفین' })).toBeVisible();
  await admin.screenshot({ path: 'test-results/demo-02-admin-ur.png' });
  await admin.locator('.shell-header .lang-switch button[lang=en]').click();

  // 3. The new commander logs an emergency: 2 floors × 4 zones, both responders assigned.
  const cmdCtx = await context(browser);
  const cmd = await cmdCtx.newPage();
  await signIn(cmd, cmdUser, 'en', { password: cmdTemp, newPassword: NEW_PASSWORD });
  await expect(cmd.getByTestId('live-empty')).toBeVisible();
  await cmd.getByTestId('open-dispatch').click();
  await cmd.locator('#f-address').fill(`Demo plaza ${stamp}, Mall Road`);
  await cmd.locator('#f-floors').fill('2');
  await cmd.locator('#f-zpf').fill('4');
  await cmd.locator('.add-row-btn').click();
  for (const [i, r, zone] of [
    [0, respA, 'F1-Z2'],
    [1, respB, 'F2-Z1'],
  ] as const) {
    const row = cmd.getByTestId(`team-row-${i}`);
    await row.getByLabel('Responder').selectOption({ label: r.name });
    await row.getByLabel('Zone', { exact: true }).selectOption(zone);
  }
  await cmd.getByTestId('dispatch-submit').click();
  await expect(cmd.getByTestId('live-briefing')).toBeVisible();
  await expect(cmd.locator('[data-zone]')).toHaveCount(8);
  await expect(cmd.locator('[data-zone="F1-Z2"]')).toContainText(respA.name);
  await cmd.getByTestId('go-live').click();
  await expect(cmd.getByTestId('live-active')).toBeVisible();
  const incidentId = new URL(cmd.url()).searchParams.get('incident');

  // 4. Responder A streams their zone from a phone; the map changes; escalation is alerted
  //    and spoken.
  const phoneCtx = await context(browser, true);
  const phone = await phoneCtx.newPage();
  await signIn(phone, respA.username, 'en', { password: aTemp, newPassword: NEW_PASSWORD });
  await expect(phone).toHaveURL(/\/capture$/);
  await expect(phone.getByTestId('capture-zone')).toContainText('★ F1-Z2');
  const cell = cmd.locator('[data-zone="F1-Z2"]');
  await phone.getByTestId('capture-toggle').click();
  await expect(cell).not.toHaveAttribute('data-status', 'unclassified', { timeout: 6_000 });
  await expect(cell).toHaveAttribute('data-status', 'unsafe', { timeout: 40_000 });
  await expect(cmd.getByTestId('topbar')).toHaveClass(/crit/);
  await expect
    .poll(() =>
      cmd.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.join(' | ')),
    )
    .toContain('changed rapidly');
  await phone.getByTestId('capture-toggle').click();
  await phone.screenshot({ path: 'test-results/demo-04-phone.png' });
  await phoneCtx.close();

  // 5. The commander uploads a thermal video tagged to a zone: ranked victims, critical first.
  await cmd.locator('[data-nav=analysis]').click();
  await cmd.getByTestId('analysis-zone').selectOption({ label: 'F1-Z2' });
  await cmd.getByTestId('analysis-file').setInputFiles(path.join(FIXTURES, 'thermal.mp4'));
  await cmd.getByTestId('analysis-upload').click();
  await expect(cmd.getByTestId('upload-list').locator('.upload-item').first()).toHaveAttribute(
    'data-job-status',
    'done',
    { timeout: 30_000 },
  );
  await cmd.goto(`/live?incident=${incidentId}`);
  const victims = cmd.getByTestId('victim-list');
  await expect(victims.locator('li').first()).toHaveAttribute('data-band', 'critical');

  // 6. A mobile-sync payload adds victims from source "mobile".
  const api = await request.newContext({ baseURL, ignoreHTTPSErrors: true });
  const token = (
    await (
      await api.post('/api/v1/auth/login', {
        data: { username: respA.username, password: NEW_PASSWORD },
      })
    ).json()
  ).access_token as string;
  const sync = await api.post('/api/v1/sync/incidents', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      device_id: 'android-demo',
      app_version: '1.0.0',
      incidents: [
        {
          client_uuid: `demo-${stamp}`,
          started_at: new Date().toISOString(),
          linked_incident_id: incidentId,
          detections: [
            {
              client_detection_uuid: `demo-${stamp}-1`,
              captured_at: new Date().toISOString(),
              track_id: 1,
              bbox: [0.1, 0.2, 0.3, 0.8],
              posture: 'sitting',
              posture_confidence: 0.8,
              detection_confidence: 0.9,
            },
          ],
        },
      ],
    },
  });
  expect((await sync.json()).results[0].status).toBe('created');
  await expect(victims).toContainText('Mobile', { timeout: 10_000 });
  await cmd.screenshot({ path: 'test-results/demo-06-live.png', fullPage: true });

  // 7. Close with confirmation → report → EN and UR PDFs.
  await cmd.getByTestId('close-incident').click();
  await cmd.getByTestId('confirm-button').click();
  await expect(cmd.getByTestId('live-empty')).toBeVisible();
  await cmd.goto(`/reports/${incidentId}`);
  await expect(cmd.getByTestId('report-detail')).toBeVisible();
  for (const lang of ['en', 'ur'] as const) {
    const [dl] = await Promise.all([
      cmd.waitForEvent('download'),
      cmd.getByTestId(`pdf-${lang}`).click(),
    ]);
    expect(dl.suggestedFilename()).toMatch(new RegExp(`-report-${lang}\\.pdf$`));
  }

  // 8. A trainee completes a scenario; training staff see the attempt.
  const tCtx = await context(browser);
  const trainee = await tCtx.newPage();
  await signIn(trainee, 'trainee1');
  await trainee
    .locator('.scenario-card[data-scenario="Zone status: corridor after a fire (PLACEHOLDER)"]')
    .getByTestId('open-scenario')
    .click();
  await trainee.getByTestId('start-attempt').click();
  for (let item = 1; ; item++) {
    await expect(trainee.locator('.step.current')).toHaveText(String(item));
    const n = await trainee.getByTestId('target-chip').count();
    await trainee.getByTestId('target-chip').first().click();
    for (let i = 0; i < n; i++) await trainee.locator('.label-picker [data-label=caution]').click();
    if (await trainee.getByTestId('submit-attempt').count()) break;
    await trainee.getByTestId('next-item').click();
  }
  await trainee.getByTestId('submit-attempt').click();
  await expect(trainee.getByTestId('score')).toBeVisible();
  await expect(trainee.getByTestId('attempt-result')).toContainText('Agreement with the model');
  const attemptUrl = trainee.url();

  // 9. Trainees get 403 on incidents.
  const tToken = (
    await (
      await api.post('/api/v1/auth/login', { data: { username: 'trainee1', password: PASSWORD } })
    ).json()
  ).access_token as string;
  const forbidden = await api.get('/api/v1/incidents', {
    headers: { Authorization: `Bearer ${tToken}` },
  });
  expect(forbidden.status()).toBe(403);
  await api.dispose();
  await tCtx.close();

  const sCtx = await context(browser);
  const staff = await sCtx.newPage();
  await signIn(staff, 'trainer1');
  await staff.goto('/trainer/results');
  await expect(staff.getByTestId('all-attempts').locator('a[href]').first()).toBeVisible();
  await staff.goto(attemptUrl);
  await expect(staff.getByTestId('score')).toBeVisible();
  await sCtx.close();

  // 10. /admin/status shows the mock backend with model versions.
  await admin.goto('/admin/status');
  await expect(admin.locator('[data-card=ml]')).toContainText('Mock models');
  await expect(admin.locator('[data-card=ml]')).toContainText('mock-1.0');
  await admin.screenshot({ path: 'test-results/demo-10-status.png', fullPage: true });
  await adminCtx.close();
  await cmdCtx.close();
});
