import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { signIn } from './helpers';

/**
 * Every route for every role, in English and Urdu, at phone and desktop width (HANDOFF §12):
 * correct direction, no horizontal scrolling, no untranslated keys, an accessibility scan,
 * and a screenshot of each screen in test-results/screens/.
 */
const ROLES = ['admin', 'commander1', 'responder1', 'trainee1', 'trainer1'] as const;
const EXTRA: Record<string, string[]> = {
  admin: ['/admin/scenarios', '/admin/settings', '/admin/status', '/admin/audit', '/help/live'],
  commander1: ['/help/capture'],
  trainee1: ['/help/trainer'],
};
const KEY_LIKE =
  /\b(?:common|nav|pages|live|capture|analysis|reports|team|trainer|admin|help|settings|errors|status|victims|alerts|kpi|dispatch)\.[a-z][A-Za-z_]*(?:\.[A-Za-z_]+)*\b/;

async function setLang(page: Page, lang: 'en' | 'ur') {
  await page.locator(`.shell-header .lang-switch button[lang=${lang}]`).click();
  await expect(page.locator('html')).toHaveAttribute('dir', lang === 'ur' ? 'rtl' : 'ltr');
}

for (const role of ROLES) {
  test(`${role}: every screen in both languages`, async ({ page }) => {
    test.setTimeout(240_000);
    await signIn(page, role);
    const routes = [
      ...(await page
        .locator('a[data-nav]')
        .evaluateAll((els) => els.map((e) => e.getAttribute('href')!))),
      ...(EXTRA[role] ?? []),
    ];
    const problems: string[] = [];
    try {
      for (const lang of ['en', 'ur'] as const) {
        await setLang(page, lang);
        for (const width of [1280, 360]) {
          await page.setViewportSize({ width, height: width === 360 ? 740 : 900 });
          for (const route of routes) {
            await page.goto(route);
            await page.waitForLoadState('networkidle');
            await expect(page.locator('html')).toHaveAttribute(
              'dir',
              lang === 'ur' ? 'rtl' : 'ltr',
            );
            const where = `${route} [${lang} ${width}px]`;
            const overflow = await page.evaluate(
              () => document.documentElement.scrollWidth - window.innerWidth,
            );
            if (overflow > 1) problems.push(`${where}: horizontal overflow ${overflow}px`);
            const key = (await page.locator('main, .app-main, body').first().innerText()).match(
              KEY_LIKE,
            );
            if (key) problems.push(`${where}: untranslated key "${key[0]}"`);
            const name = `${role}${route.replace(/\//g, '_')}-${lang}-${width}`;
            await page.screenshot({ path: `test-results/screens/${name}.png`, fullPage: true });
            if (width === 1280) {
              const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
              for (const v of axe.violations.filter(
                (x) => x.impact === 'serious' || x.impact === 'critical',
              ))
                problems.push(
                  `${where}: a11y ${v.id} (${v.nodes.length}) ${v.nodes[0]?.target.join(' ')}`,
                );
            }
          }
        }
      }
    } finally {
      await page.setViewportSize({ width: 1280, height: 900 });
      await setLang(page, 'en');
    }
    expect(problems, problems.join('\n')).toEqual([]);
  });
}
