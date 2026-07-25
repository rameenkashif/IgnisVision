import { useNavigate } from 'react-router-dom';
import { BrandMark } from '../components/BrandMark';
import { useLanguage } from '../state/LanguageContext';
import './Dashboard.css';

export function Dashboard() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  return (
    <div className="dash-placeholder">
      <BrandMark size={56} />
      <h1>{t('dashboardComingSoon')}</h1>
      <p>{t('dashboardNote')}</p>
      <button className="dash-logout" onClick={() => navigate('/login')}>
        {t('logOut')}
      </button>
    </div>
  );
}
