import { expect, test } from '@playwright/test';
import { navKeys, signIn } from './helpers';

/** Phase 2 exit: log in as each role and see the right navigation in both languages. */
const EXPECTED: Record<string, { nav: string[]; home: string; label: { en: string; ur: string } }> =
  {
    admin: {
      nav: ['live', 'reports', 'team', 'trainerResults', 'admin', 'settings', 'help'],
      home: '/live',
      label: { en: 'Administration', ur: 'انتظامیہ' },
    },
    commander1: {
      nav: [
        'live',
        'capture',
        'analysis',
        'reports',
        'team',
        'trainer',
        'trainerResults',
        'settings',
        'help',
      ],
      home: '/live',
      label: { en: 'Live monitoring', ur: 'براہِ راست نگرانی' },
    },
    responder1: {
      nav: ['capture', 'analysis', 'team', 'trainer', 'settings', 'help'],
      home: '/capture',
      label: { en: 'Zone capture', ur: 'زون کیپچر' },
    },
    trainee1: {
      nav: ['trainer', 'settings', 'help'],
      home: '/trainer',
      label: { en: 'Training simulator', ur: 'تربیتی سمیولیٹر' },
    },
    trainer1: {
      nav: ['trainer', 'trainerResults', 'settings', 'help'],
      home: '/trainer',
      label: { en: 'Training simulator', ur: 'تربیتی سمیولیٹر' },
    },
  };

for (const [username, exp] of Object.entries(EXPECTED)) {
  test(`${username}: role navigation in English and Urdu`, async ({ page }) => {
    await signIn(page, username, 'en');
    await expect(page).toHaveURL(new RegExp(`${exp.home}$`));
    expect(await navKeys(page)).toEqual(exp.nav);
    await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
    await expect(page.getByTestId('side-nav')).toContainText(exp.label.en);
    await expect(page.getByTestId('conn-indicator')).toBeVisible();
    await expect(page.getByTestId('help-button')).toBeVisible();

    // Switch to Urdu from the shell: RTL, translated nav, same page (no state loss).
    const before = page.url();
    await page.locator('.shell-header .lang-switch button[lang=ur]').click();
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ur');
    await expect(page.getByTestId('side-nav')).toContainText(exp.label.ur);
    expect(await navKeys(page)).toEqual(exp.nav);
    expect(page.url()).toBe(before);
    await page.screenshot({ path: `test-results/shell-${username}-ur.png`, fullPage: true });

    // Language is saved to the profile: survives a reload.
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await page.locator('.shell-header .lang-switch button[lang=en]').click();
    await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  });
}

test('trainee opening an incident screen sees "not available for your role"', async ({ page }) => {
  await signIn(page, 'trainee1');
  await page.goto('/live');
  await expect(page.getByTestId('forbidden')).toBeVisible();
});

test('camera indicator only on camera screens; help deep-links to the screen topic', async ({
  page,
}) => {
  await signIn(page, 'commander1');
  await expect(page.getByTestId('cam-indicator')).toHaveCount(0);
  await page.locator('[data-nav=capture]').click();
  await expect(page.getByTestId('cam-indicator')).toBeVisible();
  await page.getByTestId('help-button').click();
  await expect(page).toHaveURL(/\/help\/capture$/);
  await expect(page.getByTestId('help-capture')).toBeVisible();
});

test('sign out returns to sign-in and the session is gone', async ({ page }) => {
  await signIn(page, 'commander1');
  await page.locator('.signout').click();
  await expect(page).toHaveURL(/\/signin$/);
  await page.goto('/live');
  await expect(page).toHaveURL(/\/signin$/);
});

test('wrong password shows a translated error', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('iv.splashSeen', '1'));
  await page.goto('/signin');
  await page.locator('.onboard-top .lang-switch button[lang=ur]').click();
  await page.locator('#username').fill('commander1');
  await page.locator('#password').fill('not-the-password1');
  await page.locator('form button[type=submit]').click();
  await expect(page.getByRole('alert')).toHaveText('یوزر نیم یا پاس ورڈ درست نہیں۔');
});

test.describe('phone (360px)', () => {
  test.use({ viewport: { width: 360, height: 740 }, hasTouch: true, isMobile: true });

  test('sidebar becomes a drawer; touch targets are at least 48px', async ({ page }) => {
    await signIn(page, 'responder1');
    const menu = page.getByRole('button', { name: 'Open menu' });
    await expect(menu).toBeVisible();
    const box = await menu.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(48);
    await menu.click();
    await expect(page.locator('#sidebar')).toHaveCSS('transform', 'none');
    const capture = page.locator('[data-nav=capture]');
    await expect(capture).toBeInViewport();
    expect((await capture.boundingBox())!.height).toBeGreaterThanOrEqual(48);
    const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollW).toBeLessThanOrEqual(360);
    await page.screenshot({ path: 'test-results/shell-phone-drawer.png' });
    await page.locator('.scrim.show').click({ position: { x: 340, y: 400 } });
    await expect(page.locator('#sidebar')).not.toHaveClass(/open/);
    await page.screenshot({ path: 'test-results/shell-phone.png' });
  });
});
