import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type Lang = 'en' | 'ur';

const STORAGE_KEY = 'iv-lang';

const dict = {
  en: {
    appName: 'Ignis Vision',
    tagline: 'AI Fire Intelligence',
    loginTitle: 'Incident Commander Console',
    loginSubtitle: 'Sign in to access live monitoring',
    username: 'Username',
    password: 'Password',
    signIn: 'Sign in',
    loginNote: 'Mock login — authentication is not wired up yet.',
    chooseLanguage: 'Choose your language',
    chooseLanguageSubtitle: 'You can change this later in settings.',
    continue: 'Continue',
    dashboardComingSoon: 'Dashboard — coming online',
    dashboardNote:
      'The full Commander Dashboard (live monitoring, zone map, alerts) is being rebuilt next.',
    logOut: 'Log out',
  },
  ur: {
    appName: 'اگنس ویژن',
    tagline: 'اے آئی فائر انٹیلیجنس',
    loginTitle: 'انسیڈنٹ کمانڈر کنسول',
    loginSubtitle: 'لائیو مانیٹرنگ تک رسائی کے لیے سائن ان کریں',
    username: 'صارف کا نام',
    password: 'پاس ورڈ',
    signIn: 'سائن ان',
    loginNote: 'ابھی یہ صرف نمائشی لاگ ان ہے — تصدیق فعال نہیں کی گئی۔',
    chooseLanguage: 'اپنی زبان منتخب کریں',
    chooseLanguageSubtitle: 'آپ بعد میں سیٹنگز میں یہ تبدیل کر سکتے ہیں۔',
    continue: 'جاری رکھیں',
    dashboardComingSoon: 'ڈیش بورڈ — تیار ہو رہا ہے',
    dashboardNote:
      'مکمل کمانڈر ڈیش بورڈ (لائیو مانیٹرنگ، زون میپ، الرٹس) اگلے مرحلے میں بنایا جائے گا۔',
    logOut: 'لاگ آؤٹ',
  },
} as const;

type DictKey = keyof (typeof dict)['en'];

interface LanguageContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: DictKey) => string;
  dir: 'ltr' | 'rtl';
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === 'ur' || stored === 'en' ? stored : 'en';
  });

  const setLang = (next: Lang) => {
    setLangState(next);
    localStorage.setItem(STORAGE_KEY, next);
  };

  const dir = lang === 'ur' ? 'rtl' : 'ltr';

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      lang,
      setLang,
      dir,
      t: (key: DictKey) => dict[lang][key],
    }),
    [lang, dir],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider');
  return ctx;
}
