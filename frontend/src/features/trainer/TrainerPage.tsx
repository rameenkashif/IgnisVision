import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useAttempts, useScenarios } from '../../api/training';
import { PageHeader } from '../../components/PageHeader';
import { formatDateTime } from '../../lib/format';
import { useAuth } from '../../stores/auth';
import { pct, pick } from './util';

/** Scenario picker + the user's own recent attempts (SRS UC-06). */
export function TrainerPage() {
  const { t } = useTranslation();
  const me = useAuth((s) => s.user!);
  const scenarios = useScenarios();
  const mine = useAttempts({ user_id: me.id });

  return (
    <>
      <PageHeader page="trainer" />
      {scenarios.data && scenarios.data.length === 0 && (
        <div className="empty-state">
          <p>{t('trainer.noScenarios')}</p>
        </div>
      )}
      <div className="scenario-grid" data-testid="scenario-list">
        {scenarios.data?.map((s) => (
          <article key={s.id} className="scenario-card" data-scenario={s.title_en}>
            <div className="scenario-tags">
              <span className="tag">{t(`trainer.kind.${s.kind}`)}</span>
              <span className="tag" aria-label={t('trainer.difficulty', { n: s.difficulty })}>
                {'●'.repeat(s.difficulty)}
                <span className="dim">{'●'.repeat(Math.max(0, 5 - s.difficulty))}</span>
              </span>
              {s.is_placeholder && <span className="tag warn">{t('trainer.placeholder')}</span>}
            </div>
            <h2>{pick(s.title_en, s.title_ur)}</h2>
            <p className="muted">{pick(s.description_en, s.description_ur)}</p>
            <div className="scenario-meta">
              <span>{t('trainer.items', { count: s.item_count })}</span>
              {(s.attempts ?? 0) > 0 && (
                <span>
                  {t('trainer.best', { score: pct(s.best_score) })} ·{' '}
                  {t('trainer.tries', { count: s.attempts ?? 0 })}
                </span>
              )}
            </div>
            <Link className="btn primary" to={`/trainer/${s.id}`} data-testid="open-scenario">
              {(s.attempts ?? 0) > 0 ? t('trainer.retry') : t('trainer.start')}
            </Link>
          </article>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{t('trainer.myAttempts')}</h2>
        </div>
        <div className="panel-body table-wrap">
          {mine.data?.length ? (
            <table className="table" data-testid="my-attempts">
              <thead>
                <tr>
                  <th>{t('trainer.scenario')}</th>
                  <th>{t('trainer.submitted')}</th>
                  <th>{t('trainer.score')}</th>
                  <th>{t('trainer.agreement')}</th>
                </tr>
              </thead>
              <tbody>
                {mine.data.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <Link to={`/trainer/attempts/${a.id}`}>
                        {pick(a.scenario_title_en, a.scenario_title_ur)}
                      </Link>
                    </td>
                    <td>{formatDateTime(a.submitted_at)}</td>
                    <td>{pct(a.score_pct)}</td>
                    <td>{pct(a.model_agreement_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">{t('trainer.noAttempts')}</p>
          )}
        </div>
      </div>
    </>
  );
}
