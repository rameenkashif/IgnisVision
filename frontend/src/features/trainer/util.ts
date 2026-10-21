import { currentLang } from '../../i18n';

/** Bilingual content field for the current UI language (falls back to English). */
export function pick(en: string | null | undefined, ur: string | null | undefined): string {
  return (currentLang() === 'ur' ? ur || en : en || ur) ?? '';
}

export function pct(v: number | null | undefined): string {
  return v == null ? '—' : `${Math.round(v)}%`;
}
