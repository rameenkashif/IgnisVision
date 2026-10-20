import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { BrandMark } from '../../components/BrandMark';
import type { Lang } from '../../i18n';
import { setLanguage } from '../../lib/session';

/** First-time language choice (saved to the profile and this device). */
export function Language() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  async function choose(lang: Lang) {
    await setLanguage(lang);
    navigate('/onboarding', { replace: true });
  }

  return (
    <div className="onboard-screen">
      <div className="gradient-bg" aria-hidden="true" />
      <div className="onboard-card">
        <div className="onboard-brand">
          <BrandMark large />
          <div>
            <h1>{t('language.title')}</h1>
            <p>{t('language.subtitle')}</p>
          </div>
        </div>
        <div className="lang-choice-grid">
          <button type="button" className="lang-choice" lang="en" onClick={() => void choose('en')}>
            <div className="glyph">EN</div>
            <div className="name">English</div>
          </button>
          <button type="button" className="lang-choice" lang="ur" onClick={() => void choose('ur')}>
            <div className="glyph ur">اردو</div>
            <div className="name">Urdu</div>
          </button>
        </div>
        <div className="onboard-foot-link">{t('language.hint')}</div>
      </div>
    </div>
  );
}
