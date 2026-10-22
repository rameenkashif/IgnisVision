import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  downloadReportPdf,
  useDeleteIncident,
  useRegenerateReport,
  useReport,
} from '../../api/reports';
import { ConfirmDialog } from '../../components/Modal';
import { PageHeader } from '../../components/PageHeader';
import { RpiChip } from '../../components/RpiChip';
import { currentLang } from '../../i18n';
import { formatDateTime, formatTime } from '../../lib/format';
import { useAuth } from '../../stores/auth';

/* The stats blob is free-form JSON from the backend (services/reports.compile_stats). */
type Transition = { at: string; status: string };
type ZoneRow = {
  code: string;
  label: string | null;
  floor: number | null;
  final_status: string;
  final_at: string | null;
  peak_status: string;
  assessments: number;
  transitions: Transition[];
};
type VictimRow = {
  rank: number | null;
  posture: string;
  low_confidence: boolean;
  band: 'critical' | 'high' | 'medium' | 'low';
  score: number;
  zone: string | null;
  status: string;
  first_seen_at: string | null;
};
type TeamRow = {
  responder: string | null;
  zone: string | null;
  device: string | null;
  assigned_at: string | null;
  unassigned_at: string | null;
};
type AlertRow = {
  severity: string;
  message_key: string;
  params: Record<string, unknown>;
  at: string;
};
type Event = { at: string; key: string; params: Record<string, unknown> };
type Stats = {
  incident: {
    code: string;
    address: string | null;
    city: string | null;
    opened_at: string;
    closed_at: string | null;
    commander: string | null;
  };
  duration_s: number | null;
  counts: {
    zones: number;
    responders: number;
    victims: number;
    rescued: number;
    peak_status: string;
    alerts_by_severity: Record<string, number>;
  };
  zones: ZoneRow[];
  team: TeamRow[];
  victims: VictimRow[];
  alerts: AlertRow[];
  timeline: Event[];
  timeline_truncated: number;
  model_versions: string[];
};

const STATUSES = ['safe', 'caution', 'unsafe', 'blocked', 'unclassified'];

function duration(s: number | null): string {
  if (s == null) return '—';
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

function messageText(t: TFunction, key: string, params: Record<string, unknown>): string {
  const p: Record<string, unknown> = { ...params };
  for (const k of ['from', 'to', 'status'])
    if (typeof p[k] === 'string') p[k] = t(`status.${p[k]}`);
  return t(key, { ...p, defaultValue: key });
}

function eventText(t: TFunction, e: Event): string {
  const p: Record<string, unknown> = { ...e.params };
  if (e.key === 'alert')
    return messageText(
      t,
      String(p.message_key),
      (p.message_params as Record<string, unknown>) ?? {},
    );
  for (const k of ['from', 'to']) if (typeof p[k] === 'string') p[k] = t(`status.${p[k]}`);
  if (typeof p.band === 'string') p.band = t(`band.${p.band}`);
  if (typeof p.posture === 'string') p.posture = t(`posture.${p.posture}`);
  if (typeof p.source === 'string')
    p.source = t(`analysis.source.${p.source}`, { defaultValue: p.source });
  return t(`reports.event.${e.key}`, p);
}

/** Per-zone status over the incident's lifetime as horizontal bars (mirrors the PDF chart). */
function HistoryChart({
  zones,
  start,
  end,
}: {
  zones: ZoneRow[];
  start: string;
  end: string | null;
}) {
  const { t } = useTranslation();
  const t0 = new Date(start).getTime();
  const t1 = Math.max(new Date(end ?? Date.now()).getTime(), t0 + 1);
  const W = 600;
  const rowH = 18;
  const labelW = 64;
  const x = (iso: string) => labelW + ((new Date(iso).getTime() - t0) / (t1 - t0)) * (W - labelW);
  const h = zones.length * rowH + 20;
  return (
    <figure className="history-chart">
      <svg
        viewBox={`0 0 ${W} ${h}`}
        role="img"
        aria-label={t('reports.history')}
        style={{ direction: 'ltr' }}
      >
        {zones.map((z, i) => {
          const segs = [{ at: start, status: 'unclassified' }, ...z.transitions];
          return (
            <g key={z.code} transform={`translate(0 ${i * rowH})`}>
              <text x={0} y={rowH / 2 + 4} className="lbl">
                {z.code}
              </text>
              {segs.map((s, j) => {
                const xa = x(s.at);
                const xb = j + 1 < segs.length ? x(segs[j + 1].at) : W;
                return (
                  <rect
                    key={j}
                    x={xa}
                    y={2}
                    width={Math.max(xb - xa, 0.5)}
                    height={rowH - 4}
                    fill={`var(--${s.status})`}
                  >
                    <title>{`${z.code} · ${t(`status.${s.status}`)} · ${formatTime(s.at)}`}</title>
                  </rect>
                );
              })}
            </g>
          );
        })}
        <text x={labelW} y={h - 4} className="lbl">
          {formatTime(start)}
        </text>
        <text x={W} y={h - 4} className="lbl" textAnchor="end">
          {formatTime(end ?? new Date().toISOString())}
        </text>
      </svg>
      <figcaption className="legend">
        {STATUSES.map((s) => (
          <span key={s}>
            <i style={{ background: `var(--${s})` }} /> {t(`status.${s}`)}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

function Section({
  title,
  children,
  testId,
}: {
  title: string;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <section className="panel report-section" data-testid={testId}>
      <div className="panel-head">
        <h2>{title}</h2>
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

/** Post-incident report (HANDOFF §11): narrative, figures, history and PDF export. */
export function ReportDetail() {
  const { t } = useTranslation();
  const { incidentId } = useParams();
  const navigate = useNavigate();
  const role = useAuth((s) => s.user!.role);
  const report = useReport(incidentId);
  const regenerate = useRegenerateReport(incidentId!);
  const del = useDeleteIncident();
  const [busy, setBusy] = useState<'en' | 'ur' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (report.isLoading) return <div className="loader">{t('common.loading')}</div>;
  if (report.isError || !report.data) {
    const code = (report.error as { code?: string } | null)?.code;
    return (
      <>
        <PageHeader page="reports" />
        <div className="empty-state">
          <p>{code === 'incident_not_closed' ? t('reports.notClosed') : t('errors.unknown')}</p>
          <Link to="/reports">{t('common.back')}</Link>
        </div>
      </>
    );
  }

  const r = report.data;
  const s = r.stats as unknown as Stats;
  const inc = s.incident;
  const narrative = currentLang() === 'ur' ? r.narrative_ur : r.narrative_en;

  const pdf = async (lang: 'en' | 'ur') => {
    setBusy(lang);
    setError(null);
    try {
      await downloadReportPdf(r.incident_id, inc.code, lang);
    } catch {
      setError(t('errors.unknown'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader
        page="reports"
        actions={
          <div className="report-actions">
            <button
              type="button"
              className="btn primary"
              disabled={!!busy}
              onClick={() => pdf('en')}
              data-testid="pdf-en"
            >
              {busy === 'en' ? t('reports.downloading') : t('reports.pdfEn')}
            </button>
            <button
              type="button"
              className="btn primary"
              disabled={!!busy}
              onClick={() => pdf('ur')}
              data-testid="pdf-ur"
            >
              {busy === 'ur' ? t('reports.downloading') : t('reports.pdfUr')}
            </button>
            {role === 'incident_commander' && (
              <button
                type="button"
                className="btn"
                disabled={regenerate.isPending}
                onClick={() => regenerate.mutate()}
                data-testid="regenerate"
              >
                {t('reports.regenerate')}
              </button>
            )}
            {role === 'admin' && (
              <button
                type="button"
                className="btn danger"
                onClick={() => setConfirmDelete(true)}
                data-testid="delete-incident"
              >
                {t('reports.delete')}
              </button>
            )}
          </div>
        }
      />
      {error && (
        <div className="banner bad" role="alert">
          {error}
        </div>
      )}
      {regenerate.isSuccess && (
        <div className="banner warn" role="status">
          {t('reports.regenerated')}
        </div>
      )}

      <div className="report-head" data-testid="report-detail">
        <h2 dir="ltr">{inc.code}</h2>
        <div className="muted">
          {[inc.address, inc.city].filter(Boolean).join(', ')} · {formatDateTime(inc.opened_at)} –{' '}
          {formatDateTime(inc.closed_at)}
        </div>
        <div className="muted small">
          {t('reports.generated', { time: formatDateTime(r.generated_at) })}
        </div>
      </div>
      <p className="report-disclaimer" role="note">
        {t('victims.disclaimer')}
      </p>

      <Section title={t('reports.summary')} testId="report-narrative">
        {narrative.split(/\n{2,}/).map((p, i) => (
          <p key={i} className="narrative">
            {p}
          </p>
        ))}
        {r.narrative_source === 'llm' && <p className="muted small">{t('reports.narrativeAi')}</p>}
      </Section>

      <Section title={t('reports.figures')}>
        <div className="figures">
          {[
            ['zones', s.counts.zones],
            ['responders', s.counts.responders],
            ['people', s.counts.victims],
            ['rescued', s.counts.rescued],
            ['crit', s.counts.alerts_by_severity.crit ?? 0],
            ['peak', t(`status.${s.counts.peak_status}`)],
            ['duration', duration(s.duration_s)],
          ].map(([k, v]) => (
            <div key={k} className="figure" data-fig={k}>
              <div className="v">{v}</div>
              <div className="k">{t(`reports.fig.${k}`)}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title={t('reports.zones')}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t('reports.zone')}</th>
                <th>{t('reports.label')}</th>
                <th>{t('reports.final')}</th>
                <th>{t('reports.finalAt')}</th>
                <th>{t('reports.peak')}</th>
                <th>{t('reports.analyses')}</th>
              </tr>
            </thead>
            <tbody>
              {s.zones.map((z) => (
                <tr key={z.code}>
                  <td dir="ltr">{z.code}</td>
                  <td>{z.label ?? '—'}</td>
                  <td>
                    <span className={`status-pill st-${z.final_status}`}>
                      {t(`status.${z.final_status}`)}
                    </span>
                  </td>
                  <td>{formatTime(z.final_at)}</td>
                  <td>{t(`status.${z.peak_status}`)}</td>
                  <td>{z.assessments}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title={t('reports.history')}>
        <HistoryChart zones={s.zones} start={inc.opened_at} end={inc.closed_at} />
      </Section>

      <Section title={t('reports.victims')}>
        {s.victims.length === 0 ? (
          <p className="muted">{t('reports.none2')}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t('reports.rank')}</th>
                  <th>{t('victims.band')}</th>
                  <th>{t('victims.posture')}</th>
                  <th>{t('victims.zone')}</th>
                  <th>{t('reports.cols.status')}</th>
                  <th>{t('reports.time')}</th>
                </tr>
              </thead>
              <tbody>
                {s.victims.map((v, i) => (
                  <tr key={i}>
                    <td>{v.rank ?? '—'}</td>
                    <td>
                      <RpiChip band={v.band} score={v.score} />
                    </td>
                    <td>
                      {t(`posture.${v.posture}`)}
                      {v.low_confidence && (
                        <span className="muted small"> · {t('victims.lowConfidence')}</span>
                      )}
                    </td>
                    <td dir="ltr">{v.zone ?? '—'}</td>
                    <td>{t(`victims.status.${v.status}`)}</td>
                    <td>{formatTime(v.first_seen_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={t('reports.team')}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t('reports.responder')}</th>
                <th>{t('reports.zone')}</th>
                <th>{t('reports.device')}</th>
                <th>{t('reports.from')}</th>
                <th>{t('reports.until')}</th>
              </tr>
            </thead>
            <tbody>
              {s.team.map((m, i) => (
                <tr key={i}>
                  <td>{m.responder ?? '—'}</td>
                  <td dir="ltr">{m.zone ?? '—'}</td>
                  <td>{m.device ?? '—'}</td>
                  <td>{formatTime(m.assigned_at)}</td>
                  <td>{m.unassigned_at ? formatTime(m.unassigned_at) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title={t('reports.alerts')}>
        {s.alerts.length === 0 ? (
          <p className="muted">{t('reports.none2')}</p>
        ) : (
          <ul className="report-list">
            {s.alerts.map((a, i) => (
              <li key={i} className={`sev-${a.severity}`}>
                <span className="when">{formatTime(a.at)}</span>
                <span className="sev">{t(`reports.severity.${a.severity}`)}</span>
                <span>{messageText(t, a.message_key, a.params ?? {})}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={t('reports.timeline')} testId="report-timeline">
        <ul className="report-list">
          {s.timeline.map((e, i) => (
            <li key={i}>
              <span className="when">{formatTime(e.at)}</span>
              <span>{eventText(t, e)}</span>
            </li>
          ))}
        </ul>
        {s.timeline_truncated > 0 && (
          <p className="muted small">{t('reports.truncated', { n: s.timeline_truncated })}</p>
        )}
      </Section>

      {r.frames.length > 0 && (
        <Section title={t('reports.frames')}>
          <div className="report-frames">
            {r.frames.map((f, i) =>
              f.url ? (
                <figure key={i}>
                  <img src={f.url} alt={`${f.kind} · ${f.zone ?? ''}`} loading="lazy" />
                  <figcaption>
                    <span dir="ltr">{f.zone}</span> ·{' '}
                    {f.kind === 'rgb' && f.status
                      ? t(`status.${f.status}`)
                      : f.band
                        ? t(`band.${f.band}`)
                        : ''}{' '}
                    · {formatTime(f.at)}
                  </figcaption>
                </figure>
              ) : null,
            )}
          </div>
        </Section>
      )}

      <Section title={t('reports.models')}>
        <ul className="report-models" dir="ltr">
          {s.model_versions.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </Section>

      {confirmDelete && (
        <ConfirmDialog
          title={t('reports.deleteTitle', { code: inc.code })}
          body={t('reports.deleteBody')}
          confirmLabel={t('reports.delete')}
          busy={del.isPending}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() =>
            del.mutate(r.incident_id, {
              onSuccess: () => navigate('/reports', { replace: true }),
            })
          }
        />
      )}
    </>
  );
}
