import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type Lang = 'en' | 'ur';

const STORAGE_KEY = 'iv-lang';

const dict = {
  en: {
    appName: 'Ignis Vision',
    tagline: 'AI Fire Intelligence',
    loginTitle: 'IGNIS VISION',
    loginSubtitle: 'AI Fire Intelligence System',
    commanderId: 'Commander ID',
    password: 'Password',
    signIn: 'Sign in',
    loginFooter: 'Karachi Fire Department · Rescue 1122 partner access',
    chooseLanguage: 'Select language',
    chooseLanguageSubtitle: 'Console display language',
    dashboardComingSoon: 'Dashboard — coming online',
    dashboardNote:
      'The full Commander Dashboard (live monitoring, zone map, alerts) is being rebuilt next.',
    logOut: 'Log out',
  },
  ur: {
    appName: 'اگنس ویژن',
    tagline: 'اے آئی فائر انٹیلیجنس',
    loginTitle: 'اگنس ویژن',
    loginSubtitle: 'اے آئی فائر انٹیلیجنس سسٹم',
    commanderId: 'کمانڈر آئی ڈی',
    password: 'پاس ورڈ',
    signIn: 'سائن ان',
    loginFooter: 'کراچی فائر ڈیپارٹمنٹ · ریسکیو 1122 پارٹنر رسائی',
    chooseLanguage: 'زبان منتخب کریں',
    chooseLanguageSubtitle: 'کنسول ڈسپلے زبان',
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
