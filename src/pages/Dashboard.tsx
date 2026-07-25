import { useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { useLanguage } from '../state/LanguageContext';
import '../styles/ambient.css';
import './Dashboard.css';

export function Dashboard() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  return (
    <div className="dash-placeholder ambient-glow">
      <Logo height={72} glow />
      <h1>{t('dashboardComingSoon')}</h1>
      <p>{t('dashboardNote')}</p>
      <button className="dash-logout" onClick={() => navigate('/login')}>
        {t('logOut')}
      </button>
    </div>
  );
}
