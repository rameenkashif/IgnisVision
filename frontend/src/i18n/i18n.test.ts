import en from './en.json';
import ur from './ur.json';
import i18n, { errorMessage } from '.';

function flatten(o: object, prefix = ''): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    v && typeof v === 'object' ? flatten(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe('i18n', () => {
  it('English and Urdu have exactly the same keys', () => {
    expect(flatten(ur).sort()).toEqual(flatten(en).sort());
  });

  it('every Urdu string is non-empty and keeps interpolation placeholders', () => {
    const get = (o: Record<string, unknown>, path: string) =>
      path.split('.').reduce<unknown>((a, k) => (a as Record<string, unknown>)[k], o) as string;
    for (const key of flatten(en)) {
      const e = get(en, key);
      const u = get(ur, key);
      expect(u.trim(), key).not.toBe('');
      for (const ph of e.match(/{{\w+}}/g) ?? []) expect(u, key).toContain(ph);
    }
  });

  it('switching to Urdu sets lang and right-to-left direction', async () => {
    await i18n.changeLanguage('ur');
    expect(document.documentElement.lang).toBe('ur');
    expect(document.documentElement.dir).toBe('rtl');
    expect(localStorage.getItem('iv.lang')).toBe('ur');
    await i18n.changeLanguage('en');
    expect(document.documentElement.dir).toBe('ltr');
  });

  it('translates backend error codes, with a fallback', async () => {
    await i18n.changeLanguage('en');
    expect(errorMessage('invalid_credentials')).toBe('Username or password is incorrect.');
    expect(errorMessage('some_new_code')).toBe(en.errors.unknown);
  });
});
