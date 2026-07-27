import { useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { useLanguage } from '../state/LanguageContext';
import type { Lang } from '../state/LanguageContext';
import '../styles/ambient.css';
import '../components/AuthShell.css';
import './LanguageSelect.css';

const OPTIONS: { code: Lang; glyph: string; label: string }[] = [
  { code: 'en', glyph: 'EN', label: 'English' },
  { code: 'ur', glyph: 'اردو', label: 'Urdu' },
];

export function LanguageSelect() {
  const navigate = useNavigate();
  const { setLang, t } = useLanguage();

  function choose(code: Lang) {
    setLang(code);
    navigate('/dashboard/live');
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
            <button key={opt.code} type="button" className="lang-option" onClick={() => choose(opt.code)}>
              <span className="lang-native">{opt.glyph}</span>
              <span className="lang-label">{opt.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
