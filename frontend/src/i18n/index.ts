import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import ur from './ur.json';

export type Lang = 'en' | 'ur';
export const LANGS: Lang[] = ['en', 'ur'];
const STORAGE_KEY = 'iv.lang';

function stored(): Lang | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === 'en' || v === 'ur' ? v : null;
  } catch {
    return null;
  }
}

function initial(): Lang {
  return stored() ?? (navigator.language?.toLowerCase().startsWith('ur') ? 'ur' : 'en');
}

export function applyDocumentLanguage(lang: Lang): void {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ur' ? 'rtl' : 'ltr';
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, ur: { translation: ur } },
  lng: initial(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  returnNull: false,
});
applyDocumentLanguage(i18n.language as Lang);

i18n.on('languageChanged', (lng) => {
  const lang: Lang = lng === 'ur' ? 'ur' : 'en';
  applyDocumentLanguage(lang);
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* private mode: preference just isn't remembered */
  }
});

export function currentLang(): Lang {
  return i18n.language === 'ur' ? 'ur' : 'en';
}

/** Translate a backend error envelope code, falling back to a generic message. */
export function errorMessage(code: string | undefined): string {
  const key = `errors.${code ?? 'unknown'}`;
  return i18n.exists(key) ? i18n.t(key) : i18n.t('errors.unknown');
}

export default i18n;
