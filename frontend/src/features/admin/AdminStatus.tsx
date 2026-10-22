import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useSystemStatus } from '../../api/admin';
import { PageHeader } from '../../components/PageHeader';
import { formatDateTime, formatTime } from '../../lib/format';
import { AdminTabs } from './AdminTabs';

function bytes(n: number | null | undefined): string {
  if (n == null) return '—';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v < 10 && i ? v.toFixed(1) : Math.round(v)} ${u[i]}`;
}

function duration(s: number): string {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}

function Card({
  title,
  state,
  children,
  id,
}: {
  title: string;
  state: 'ok' | 'warn';
  children: ReactNode;
  id: string;
}) {
  const { t } = useTranslation();
  return (
    <section className={`status-card ${state}`} data-card={id}>
      <header>
        <h2>{title}</h2>
        <span className={`status-dot ${state}`}>{t(`admin.status.state.${state}`)}</span>
      </header>
      <dl>{children}</dl>
    </section>
  );
}

const Row = ({ k, v }: { k: string; v: ReactNode }) => (
  <>
    <dt>{k}</dt>
    <dd>{v}</dd>
  </>
);

/** System status (SRS §4.8): one card per component, refreshed every 15 s. */
export function AdminStatus() {
  const { t } = useTranslation();
  const q = useSystemStatus();
  const s = q.data;
  const w = (k: string) => (s?.warnings.includes(k) ? 'warn' : 'ok');

  return (
    <>
      <PageHeader page="admin" />
      <AdminTabs />
      {!s ? (
        <div className="loader">{q.isError ? t('errors.unknown') : t('common.loading')}</div>
      ) : (
        <>
          <div
            className={`banner ${s.status === 'ok' ? 'ok' : 'warn'}`}
            role="status"
            data-testid="status-overall"
          >
            <span>
              {s.status === 'ok' ? t('admin.status.allOk') : t('admin.status.needsAttention')}
              {s.warnings.length > 0 && ': '}
              {s.warnings.map((k) => t(`admin.status.warn.${k}`, { defaultValue: k })).join(' · ')}
            </span>
            <span className="muted small">
              {t('admin.status.checked', { time: formatTime(s.checked_at, true) })}
            </span>
          </div>
          <div className="status-grid">
            <Card id="app" title={t('admin.status.app')} state="ok">
              <Row
                k={t('admin.status.version')}
                v={
                  <span dir="ltr">
                    {s.app.version} ({s.app.environment})
                  </span>
                }
              />
              <Row k={t('admin.status.uptime')} v={duration(s.app.uptime_s)} />
              <Row k={t('admin.status.openIncidents')} v={s.live.open_incidents} />
              <Row k={t('admin.status.liveConnections')} v={s.live.live_connections} />
            </Card>
            <Card id="db" title={t('admin.status.db')} state={s.database.ok ? 'ok' : 'warn'}>
              <Row k={t('admin.status.latency')} v={`${s.database.latency_ms} ms`} />
              <Row k={t('admin.status.size')} v={bytes(s.database.size_bytes)} />
              <Row
                k={t('admin.status.server')}
                v={<span dir="ltr">PostgreSQL {s.database.server_version}</span>}
              />
              <Row
                k={t('admin.status.migration')}
                v={<code dir="ltr">{s.database.migration}</code>}
              />
            </Card>
            <Card id="ml" title={t('admin.status.ml')} state={w('ml_fallback')}>
              <Row
                k={t('admin.status.backend')}
                v={
                  <>
                    <b>
                      {s.ml.backend === 'mock' ? t('admin.status.mock') : t('admin.status.real')}
                    </b>{' '}
                    · {s.ml.device}
                    {s.ml.mock_scenario && <span className="muted"> · {s.ml.mock_scenario}</span>}
                  </>
                }
              />
              {Object.entries(s.ml.models).map(([name, ver]) => (
                <Row key={name} k={name} v={<code dir="ltr">{ver}</code>} />
              ))}
              {s.ml.fallback_reason && (
                <Row
                  k={t('admin.status.fallback')}
                  v={<span className="error-text">{s.ml.fallback_reason}</span>}
                />
              )}
            </Card>
            <Card id="jobs" title={t('admin.status.jobs')} state={w('jobs_failed')}>
              <Row
                k={t('admin.status.queue')}
                v={`${s.jobs.queue_depth} · ${t('admin.status.workers', { n: s.jobs.workers })}`}
              />
              {(['queued', 'running', 'done', 'failed'] as const).map((k) => (
                <Row key={k} k={t(`admin.status.job.${k}`)} v={s.jobs.by_status[k] ?? 0} />
              ))}
              <Row k={t('admin.status.failed24')} v={s.jobs.failed_24h} />
            </Card>
            <Card id="storage" title={t('admin.status.storage')} state={w('disk_low')}>
              <Row
                k={t('admin.status.media')}
                v={`${s.storage.media_files} · ${bytes(s.storage.media_bytes)}`}
              />
              <Row
                k={t('admin.status.diskFree')}
                v={`${bytes(s.storage.disk_free)} / ${bytes(s.storage.disk_total)}`}
              />
            </Card>
            <Card
              id="backups"
              title={t('admin.status.backups')}
              state={s.backups.available && !s.backups.stale ? 'ok' : 'warn'}
            >
              {s.backups.available ? (
                <>
                  <Row k={t('admin.status.lastBackup')} v={formatDateTime(s.backups.last_at)} />
                  <Row k={t('admin.status.backupFiles')} v={s.backups.count} />
                  <Row
                    k={t('admin.status.latestFile')}
                    v={<code dir="ltr">{s.backups.latest_file ?? '—'}</code>}
                  />
                  <Row k={t('admin.status.size')} v={bytes(s.backups.latest_bytes)} />
                </>
              ) : (
                <Row k={t('admin.status.lastBackup')} v={t('admin.status.backupsHidden')} />
              )}
            </Card>
            <Card id="llm" title={t('admin.status.llm')} state={w('llm_key_missing')}>
              <Row
                k={t('admin.status.provider')}
                v={
                  s.llm.active ? <span dir="ltr">{s.llm.model}</span> : t('admin.status.templates')
                }
              />
              {Object.entries(s.llm.features).map(([k, on]) => (
                <Row
                  key={k}
                  k={t(`admin.set.f.llm.features.${k}`)}
                  v={on ? t('common.on') : t('common.off')}
                />
              ))}
            </Card>
            <Card id="users" title={t('admin.status.users')} state="ok">
              {Object.entries(s.users.active_by_role).map(([r, n]) => (
                <Row key={r} k={t(`roles.${r}`)} v={n} />
              ))}
              <Row k={t('admin.status.sessions')} v={s.users.active_sessions} />
            </Card>
          </div>
        </>
      )}
    </>
  );
}
