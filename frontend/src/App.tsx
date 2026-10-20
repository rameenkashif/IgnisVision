import { useEffect, useState } from 'react';
import './App.css';

type Health = { status: string; version: string; ml_backend: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch('/api/v1/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setHealth)
      .catch(() => setError(true));
  }, []);

  return (
    <main className="hello">
      <div className="brand-mark" aria-hidden="true">
        IV
      </div>
      <h1>Ignis Vision</h1>
      <p className="sub">Rescue 1122 · Incident Command</p>
      <p className="status" role="status">
        {error ? (
          <span className="chip chip-unsafe">API unreachable</span>
        ) : health ? (
          <span className="chip chip-safe">
            API {health.status} · v{health.version} · ML {health.ml_backend}
          </span>
        ) : (
          <span className="chip">Checking API…</span>
        )}
      </p>
    </main>
  );
}
