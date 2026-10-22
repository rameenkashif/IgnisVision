import { HELP_TOPICS, helpText } from './help';

test('every help topic has an English and an Urdu page with the same sections', () => {
  for (const topic of HELP_TOPICS) {
    const en = helpText(topic, 'en');
    const ur = helpText(topic, 'ur');
    expect(en.startsWith('# '), topic).toBe(true);
    expect(ur.startsWith('# '), topic).toBe(true);
    expect(ur).not.toBe(en);
    expect(/[؀-ۿ]/.test(ur), topic).toBe(true);
    const sections = (s: string) => s.split('\n').filter((l) => l.startsWith('## ')).length;
    expect(sections(ur), topic).toBe(sections(en));
  }
});
