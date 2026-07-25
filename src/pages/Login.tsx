import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { BrandMark } from '../components/BrandMark';
import { useLanguage } from '../state/LanguageContext';
import '../components/AuthShell.css';
import './Login.css';

export function Login() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    navigate('/language');
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-card-head">
          <BrandMark size={44} />
          <h1>{t('loginTitle')}</h1>
          <p>{t('loginSubtitle')}</p>
        </div>

        <label className="login-field">
          <span>{t('username')}</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="commander@ignisvision"
            autoComplete="username"
          />
        </label>

        <label className="login-field">
          <span>{t('password')}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </label>

        <button type="submit" className="login-submit">
          {t('signIn')}
        </button>

        <p className="login-note">{t('loginNote')}</p>
      </form>
    </div>
  );
}
