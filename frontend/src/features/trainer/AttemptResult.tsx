import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAttempt, type ItemResult, type StageItem } from '../../api/training';
import { PageHeader } from '../../components/PageHeader';
import { formatDateTime } from '../../lib/format';
import { canAccess } from '../../lib/nav';
import { reasonText } from '../../lib/reasons';
import { useAuth } from '../../stores/auth';
import { MediaStage } from './MediaStage';
import { pct, pick } from './util';

type View = 'answer' | 'truth' | 'model';
type Reason = { key: string; params?: Record<string, unknown> };

const labelOf = (t: TFunction, type: string, v: string | null | undefined) =>
  v ? t(type === 'zone' ? `status.${v}` : `posture.${v}`) : '';

function ItemCard({ item, n }: { item: ItemResult; n: number }) {
  const { t } = useTranslation();
  const [view, setView] = useState<View>('answer');
  const byId = Object.fromEntries(item.targets.map((r) => [r.id, r]));
  const ids = (item.type === 'zone' ? item.regions : item.people).map((x) => x.id);
  const value = (id: string) => {
    const r = byId[id];
    if (!r) return null;
    return view === 'answer' ? r.answer : view === 'truth' ? r.truth : r.model;
  };
  const missing = t(item.type === 'zone' ? 'trainer.notAnalysable' : 'trainer.noModel');
  const labels = Object.fromEntries(
    ids.map((id) => {
      const r = byId[id];
      const v = value(id);
      const tone =
        view === 'answer'
          ? r?.correct
            ? 'ok'
            : r && r.credit > 0
              ? 'part'
              : 'bad'
          : `ans-${v ?? 'none'}`;
      return [id, { text: v ? labelOf(t, item.type, v) : missing, tone }];
    }),
  );
  const ref = (item.reference_output ?? {}) as {
    regions?: Record<string, { reasons?: Reason[]; confidence?: number }>;
    people?: Record<string, { posture_confidence?: number; detected?: boolean }>;
  };
  const gt = (item.ground_truth ?? {}) as { explanation_en?: string; explanation_ur?: string };

  return (
    <section className="panel result-item" data-testid="result-item">
      <div className="panel-head">
        <h2>{t('trainer.itemN', { n })}</h2>
        <span className="meta">{pct((item.score ?? 0) * 100)}</span>
      </div>
      <div className="panel-body result-grid">
        <div>
          <div className="seg" role="group" aria-label={t('trainer.show')}>
            {(['answer', 'truth', 'model'] as View[]).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                data-view={v}
              >
                {t(`trainer.view.${v}`)}
              </button>
            ))}
          </div>
          <MediaStage
            item={item as StageItem}
            labels={labels}
            shapeClass={(id) => (byId[id]?.correct ? 'ok' : 'bad')}
          />
        </div>
        <div>
          <div className="table-wrap">
            <table className="table result-table">
              <thead>
                <tr>
                  <th>{t('trainer.target')}</th>
                  <th>{t('trainer.view.answer')}</th>
                  <th>{t('trainer.view.truth')}</th>
                  <th>{t('trainer.view.model')}</th>
                  <th>{t('trainer.verdict')}</th>
                </tr>
              </thead>
              <tbody>
                {ids.map((id, i) => {
                  const r = byId[id];
                  if (!r) return null;
                  return (
                    <tr key={id} data-target={id} data-correct={r.correct}>
                      <td>
                        {t(item.type === 'zone' ? 'trainer.region' : 'trainer.person', {
                          n: i + 1,
                        })}
                      </td>
                      <td>{labelOf(t, item.type, r.answer) || '—'}</td>
                      <td>
                        <b>{labelOf(t, item.type, r.truth)}</b>
                      </td>
                      <td>
                        {r.model ? (
                          labelOf(t, item.type, r.model)
                        ) : (
                          <span className="muted">{t('trainer.noModel')}</span>
                        )}
                      </td>
                      <td
                        className={r.correct ? 'ok-text' : r.credit > 0 ? 'part-text' : 'bad-text'}
                      >
                        {r.correct
                          ? `✓ ${t('trainer.correct')}`
                          : r.credit > 0
                            ? `½ ${t('trainer.partial')}`
                            : `✕ ${t('trainer.wrong')}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {(gt.explanation_en || gt.explanation_ur) && (
            <div className="explain">
              <h3>{t('trainer.explanation')}</h3>
              <p>{pick(gt.explanation_en, gt.explanation_ur)}</p>
            </div>
          )}
          {item.type === 'zone' && ref.regions && (
            <div className="explain">
              <h3>{t('trainer.modelReasons')}</h3>
              <ul>
                {ids.map((id, i) =>
                  (ref.regions?.[id]?.reasons ?? []).map((rs, j) => (
                    <li key={`${id}-${j}`}>
                      <b>{t('trainer.region', { n: i + 1 })}:</b> {reasonText(t, rs)}
                    </li>
                  )),
                )}
              </ul>
            </div>
          )}
          <p className="muted small" dir="ltr">
            {t('trainer.modelVersion')}: {item.reference_model_version ?? '—'}
          </p>
        </div>
      </div>
    </section>
  );
}

/** Result (SRS UC-06): score vs ground truth, agreement with the model, explanations, retry. */
export function AttemptResult() {
  const { t } = useTranslation();
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const me = useAuth((s) => s.user!);
  const q = useAttempt(attemptId);

  if (q.isLoading) return <div className="loader">{t('common.loading')}</div>;
  if (!q.data)
    return (
      <>
        <PageHeader page="trainer" />
        <div className="empty-state">
          <p>{t('trainer.notFound')}</p>
        </div>
      </>
    );
  const a = q.data;
  const own = a.user_id === me.id;
  if (!a.submitted_at) {
    return (
      <>
        <PageHeader page="trainer" />
        <div className="empty-state">
          <p>{t('trainer.notSubmitted')}</p>
          <Link to={`/trainer/${a.scenario_id}`}>{t('trainer.start')}</Link>
        </div>
      </>
    );
  }
  const items = a.items;

  return (
    <>
      <PageHeader
        page="trainer"
        actions={
          <div className="row-actions">
            <Link className="btn" to={own ? '/trainer' : '/trainer/results'}>
              {t('common.back')}
            </Link>
            {own && canAccess(me.role, 'trainer') && (
              <button
                type="button"
                className="btn primary"
                onClick={() => navigate(`/trainer/${a.scenario_id}`)}
                data-testid="retry"
              >
                {t('trainer.retry')}
              </button>
            )}
          </div>
        }
      />
      <div className="result-head" data-testid="attempt-result">
        <div>
          <h2>{pick(a.scenario_title_en, a.scenario_title_ur)}</h2>
          <p className="muted">
            {own ? '' : `${a.user_name} · `}
            {formatDateTime(a.submitted_at)}
          </p>
          {a.scenario.is_placeholder && (
            <span className="tag warn">{t('trainer.placeholder')}</span>
          )}
        </div>
        <div className="figures">
          <div className="figure" data-fig="score">
            <div className="v" data-testid="score">
              {pct(a.score_pct)}
            </div>
            <div className="k">{t('trainer.scoreVsTruth')}</div>
          </div>
          <div className="figure">
            <div className="v" dir="ltr">
              {a.correct_targets} / {a.total_targets}
            </div>
            <div className="k">{t('trainer.correctTargets')}</div>
          </div>
          <div className="figure" data-fig="agreement">
            <div className="v">{pct(a.model_agreement_pct)}</div>
            <div className="k">{t('trainer.agreementLong')}</div>
          </div>
        </div>
      </div>
      {(a.llm_feedback || a.llm_feedback_pending) && (
        <section className="panel" data-testid="llm-feedback">
          <div className="panel-head">
            <h2>{t('trainer.aiFeedback')}</h2>
          </div>
          <div className="panel-body">
            {a.llm_feedback ? (
              <p className="narrative" style={{ whiteSpace: 'pre-wrap' }}>
                {a.llm_feedback}
              </p>
            ) : (
              <p className="muted">{t('trainer.aiPending')}</p>
            )}
            <p className="muted small">{t('trainer.aiNote')}</p>
          </div>
        </section>
      )}
      {items.map((it, i) => (
        <ItemCard key={it.id} item={it} n={i + 1} />
      ))}
    </>
  );
}
