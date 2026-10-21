import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useAttempts, type AttemptSummary } from '../../api/training';
import { PageHeader } from '../../components/PageHeader';
import { formatDateTime, formatTime } from '../../lib/format';
import { pct, pick } from './util';

type Trainee = { id: string; name: string; username: string; rows: AttemptSummary[] };

/** Score over time for one trainee (oldest → newest), one line per scenario is overkill for
 * a handful of attempts, so it's one line with a dot per attempt. */
function ProgressChart({ rows }: { rows: AttemptSummary[] }) {
  const { t } = useTranslation();
  const pts = [...rows].reverse();
  if (pts.length === 0) return null;
  const W = 600, H = 180, P = 28; // prettier-ignore
  const x = (i: number) => (pts.length === 1 ? W / 2 : P + (i * (W - 2 * P)) / (pts.length - 1));
  const y = (v: number) => H - P - (v / 100) * (H - 2 * P);
  return (
    <svg
      className="progress-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={t('trainer.progressChart')}
      style={{ direction: 'ltr' }}
      data-testid="progress-chart"
    >
      {[0, 50, 100].map((v) => (
        <g key={v}>
          <line x1={P} x2={W - P} y1={y(v)} y2={y(v)} className="grid" />
          <text x={4} y={y(v) + 4} className="lbl">
            {v}%
          </text>
        </g>
      ))}
      <polyline
        points={pts.map((r, i) => `${x(i)},${y(r.score_pct ?? 0)}`).join(' ')}
        className="line"
      />
      {pts.map((r, i) => (
        <circle key={r.id} cx={x(i)} cy={y(r.score_pct ?? 0)} r={4} className="dot">
          <title>{`${pick(r.scenario_title_en, r.scenario_title_ur)} · ${pct(r.score_pct)} · ${formatDateTime(r.submitted_at)}`}</title>
        </circle>
      ))}
      {pts.length > 1 && (
        <>
          <text x={P} y={H - 6} className="lbl">
            {formatTime(pts[0].submitted_at)}
          </text>
          <text x={W - P} y={H - 6} className="lbl" textAnchor="end">
            {formatTime(pts[pts.length - 1].submitted_at)}
          </text>
        </>
      )}
    </svg>
  );
}

/** All attempts for staff, commanders and admins (HANDOFF §9.6): filters, per-trainee summary
 * and progress chart. */
export function TrainerResults() {
  const { t } = useTranslation();
  const [userId, setUserId] = useState('');
  const [scenarioId, setScenarioId] = useState('');
  const all = useAttempts({});
  const rows = useMemo(() => all.data ?? [], [all.data]);

  const trainees = useMemo(() => {
    const m = new Map<string, Trainee>();
    for (const r of rows) {
      const tr = m.get(r.user_id) ?? {
        id: r.user_id,
        name: r.user_name,
        username: r.username,
        rows: [],
      };
      tr.rows.push(r);
      m.set(r.user_id, tr);
    }
    return [...m.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [rows]);
  const scenarios = useMemo(() => {
    const m = new Map<string, AttemptSummary>();
    rows.forEach((r) => m.set(r.scenario_id, r));
    return [...m.values()];
  }, [rows]);
  const shown = rows.filter(
    (r) => (!userId || r.user_id === userId) && (!scenarioId || r.scenario_id === scenarioId),
  );
  const focus =
    trainees.find((tr) => tr.id === userId) ?? (trainees.length === 1 ? trainees[0] : undefined);

  return (
    <>
      <PageHeader page="trainerResults" />
      <div className="filters" role="search">
        <label>
          <span className="field-label">{t('trainer.trainee')}</span>
          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            data-testid="filter-trainee"
          >
            <option value="">{t('reports.filters.all')}</option>
            {trainees.map((tr) => (
              <option key={tr.id} value={tr.id}>
                {tr.name} ({tr.username})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">{t('trainer.scenario')}</span>
          <select value={scenarioId} onChange={(e) => setScenarioId(e.target.value)}>
            <option value="">{t('reports.filters.all')}</option>
            {scenarios.map((s) => (
              <option key={s.scenario_id} value={s.scenario_id}>
                {pick(s.scenario_title_en, s.scenario_title_ur)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="results-grid">
        <section className="panel">
          <div className="panel-head">
            <h2>{t('trainer.trainees')}</h2>
          </div>
          <div className="panel-body table-wrap">
            <table className="table" data-testid="trainee-summary">
              <thead>
                <tr>
                  <th>{t('trainer.trainee')}</th>
                  <th>{t('trainer.attemptsCol')}</th>
                  <th>{t('trainer.avg')}</th>
                  <th>{t('trainer.bestCol')}</th>
                  <th>{t('trainer.last')}</th>
                </tr>
              </thead>
              <tbody>
                {trainees.map((tr) => {
                  const scores = tr.rows.map((r) => r.score_pct ?? 0);
                  return (
                    <tr key={tr.id} data-user={tr.username} aria-selected={tr.id === userId}>
                      <td>
                        <button type="button" className="linklike" onClick={() => setUserId(tr.id)}>
                          {tr.name}
                        </button>
                      </td>
                      <td>{tr.rows.length}</td>
                      <td>{pct(scores.reduce((a, b) => a + b, 0) / scores.length)}</td>
                      <td>{pct(Math.max(...scores))}</td>
                      <td>{formatDateTime(tr.rows[0].submitted_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!trainees.length && <p className="muted">{t('trainer.noAttempts')}</p>}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>{t('trainer.progressChart')}</h2>
            <span className="meta">{focus?.name ?? ''}</span>
          </div>
          <div className="panel-body">
            {focus ? (
              <ProgressChart rows={focus.rows} />
            ) : (
              <p className="muted">{t('trainer.pickTrainee')}</p>
            )}
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>{t('trainer.allAttempts')}</h2>
          <span className="meta">{shown.length}</span>
        </div>
        <div className="panel-body table-wrap">
          <table className="table" data-testid="all-attempts">
            <thead>
              <tr>
                <th>{t('trainer.trainee')}</th>
                <th>{t('trainer.scenario')}</th>
                <th>{t('trainer.submitted')}</th>
                <th>{t('trainer.score')}</th>
                <th>{t('trainer.agreement')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} data-user={r.username}>
                  <td>{r.user_name}</td>
                  <td>{pick(r.scenario_title_en, r.scenario_title_ur)}</td>
                  <td>{formatDateTime(r.submitted_at)}</td>
                  <td>{pct(r.score_pct)}</td>
                  <td>{pct(r.model_agreement_pct)}</td>
                  <td>
                    <Link to={`/trainer/attempts/${r.id}`}>{t('trainer.open')}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
