export const HELP_TOPICS = [
  'getting-started',
  'live',
  'capture',
  'analysis',
  'reports',
  'team',
  'trainer',
  'admin',
  'settings',
] as const;
export type HelpTopic = (typeof HELP_TOPICS)[number];

const files = import.meta.glob('../help/*/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** Bilingual Markdown help page for a topic (falls back to English). */
export function helpText(topic: string, lang: 'en' | 'ur'): string {
  return files[`../help/${lang}/${topic}.md`] ?? files[`../help/en/${topic}.md`] ?? '';
}
