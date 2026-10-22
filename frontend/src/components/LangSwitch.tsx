import { useTranslation } from 'react-i18next';
import { currentLang, LANGS } from '../i18n';
import { setLanguage } from '../lib/session';

/** EN / اردو toggle. Switching keeps all page state (SRS §5.4.6.3). */
export function LangSwitch() {
  const { t, i18n } = useTranslation();
  const lang = currentLang();
  return (
    <div
      className="lang-switch"
      role="group"
      aria-label={t('shell.language')}
      data-lang={i18n.language}
    >
      {LANGS.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={lang === l}
          onClick={() => void setLanguage(l)}
          className={l === 'ur' ? 'ur-glyph' : undefined}
        >
          {l === 'en' ? 'EN' : 'اردو'}
        </button>
      ))}
    </div>
  );
}
