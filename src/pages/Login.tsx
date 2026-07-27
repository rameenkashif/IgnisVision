import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { useLanguage } from '../state/LanguageContext';
import '../styles/ambient.css';
import '../components/AuthShell.css';
import './Login.css';

export function Login() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [commanderId, setCommanderId] = useState('rimsha.irfan');
  const [password, setPassword] = useState('');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    navigate('/language');
  }

  return (
    <div className="auth-shell ambient-glow">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-card-head">
          <Logo height={72} glow />
          <h1>{t('loginTitle')}</h1>
          <p>{t('loginSubtitle')}</p>
        </div>

        <label className="login-field">
          <span>{t('commanderId')}</span>
          <input
            value={commanderId}
            onChange={(e) => setCommanderId(e.target.value)}
            placeholder="rimsha.irfan"
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

        <p className="login-note">{t('loginFooter')}</p>
      </form>
    </div>
  );
}
