import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { useLanguage } from '../state/LanguageContext';
import type { Lang } from '../state/LanguageContext';
import '../styles/ambient.css';
import '../components/AuthShell.css';
import './LanguageSelect.css';

const OPTIONS: { code: Lang; label: string; native: string }[] = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'ur', label: 'Urdu', native: 'اردو' },
];

export function LanguageSelect() {
  const navigate = useNavigate();
  const { lang, setLang, t } = useLanguage();
  const [selected, setSelected] = useState<Lang>(lang);

  function handleContinue() {
    setLang(selected);
    navigate('/dashboard');
  }

  return (
    <div className="auth-shell ambient-glow">
      <div className="auth-card">
        <div className="auth-card-head">
          <Logo height={56} glow />
          <h1>{t('chooseLanguage')}</h1>
          <p>{t('chooseLanguageSubtitle')}</p>
        </div>

        <div className="lang-options">
          {OPTIONS.map((opt) => (
            <button
              key={opt.code}
              type="button"
              className={'lang-option' + (selected === opt.code ? ' active' : '')}
              onClick={() => setSelected(opt.code)}
            >
              <span className="lang-native">{opt.native}</span>
              <span className="lang-label">{opt.label}</span>
            </button>
          ))}
        </div>

        <button type="button" className="lang-continue" onClick={handleContinue}>
          {t('continue')}
        </button>
      </div>
    </div>
  );
}
