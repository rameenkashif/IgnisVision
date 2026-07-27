import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import '../styles/ambient.css';
import '../components/AuthShell.css';
import './Login.css';

// Always English: this screen appears before language selection in the flow.
export function Login() {
  const navigate = useNavigate();
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
          <h1>IGNIS VISION</h1>
          <p>AI Fire Intelligence System</p>
        </div>

        <label className="login-field">
          <span>Commander ID</span>
          <input
            value={commanderId}
            onChange={(e) => setCommanderId(e.target.value)}
            placeholder="rimsha.irfan"
            autoComplete="username"
          />
        </label>

        <label className="login-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </label>

        <button type="submit" className="login-submit">
          Sign in
        </button>

        <p className="login-note">Karachi Fire Department · Rescue 1122 partner access</p>
      </form>
    </div>
  );
}
