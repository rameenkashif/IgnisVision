import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '../../api/errors';
import {
  useScenario,
  useStartAttempt,
  useSubmitAttempt,
  type Answers,
  type AttemptOut,
  type StageItem,
} from '../../api/training';
import { PageHeader } from '../../components/PageHeader';
import { errorMessage } from '../../i18n';
import { LabelPicker } from './LabelPicker';
import { MediaStage } from './MediaStage';
import { pick } from './util';

type Item = AttemptOut['items'][number];

const targetsOf = (it: Item) => (it.type === 'zone' ? it.regions : it.people).map((x) => x.id);
const answerOf = (a: Answers, it: Item, id: string) =>
  it.type === 'zone' ? a[it.id]?.regions[id] : a[it.id]?.people[id];

function loadDraft(id: string): Answers {
  try {
    return JSON.parse(sessionStorage.getItem(`iv.attempt.${id}`) ?? '{}') as Answers;
  } catch {
    return {};
  }
}

/** Trainee flow (SRS UC-06): label every region and person in each item, then submit. */
export function AttemptPage() {
  const { t } = useTranslation();
  const { scenarioId } = useParams();
  const navigate = useNavigate();
  const scenario = useScenario(scenarioId);
  const start = useStartAttempt();
  const submit = useSubmitAttempt();
  const [attempt, setAttempt] = useState<AttemptOut | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Answers>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const items = useMemo(() => attempt?.items ?? [], [attempt]);
  const item = items[index];
  const remaining = items.reduce(
    (n, it) => n + targetsOf(it).filter((id) => !answerOf(answers, it, id)).length,
    0,
  );

  useEffect(() => {
    if (!attempt) return;
    try {
      sessionStorage.setItem(`iv.attempt.${attempt.id}`, JSON.stringify(answers));
    } catch {
      /* storage unavailable: the draft just isn't kept */
    }
  }, [attempt, answers]);

  useEffect(() => {
    if (item)
      setSelected(
        targetsOf(item).find((id) => !answerOf(answers, item, id)) ?? targetsOf(item)[0] ?? null,
      );
    // only when the item changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.id]);

  if (scenario.isLoading) return <div className="loader">{t('common.loading')}</div>;
  if (!scenario.data) {
    return (
      <>
        <PageHeader page="trainer" />
        <div className="empty-state">
          <p>{t('trainer.notFound')}</p>
          <Link to="/trainer">{t('common.back')}</Link>
        </div>
      </>
    );
  }
  const sc = scenario.data;

  if (!attempt || !item) {
    return (
      <>
        <PageHeader page="trainer" />
        <div className="panel attempt-intro" data-testid="scenario-intro">
          <div className="panel-body">
            {sc.is_placeholder && <p className="banner warn">{t('trainer.placeholderNote')}</p>}
            <h2>{pick(sc.title_en, sc.title_ur)}</h2>
            <p>{pick(sc.description_en, sc.description_ur)}</p>
            <p className="muted">{t('trainer.introHow', { count: sc.item_count })}</p>
            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}
            <div className="row-actions">
              <Link className="btn" to="/trainer">
                {t('common.back')}
              </Link>
              <button
                type="button"
                className="btn primary"
                disabled={start.isPending}
                data-testid="start-attempt"
                onClick={() =>
                  start.mutate(sc.id, {
                    onSuccess: (a) => {
                      setAttempt(a);
                      setAnswers(loadDraft(a.id));
                      setIndex(0);
                    },
                    onError: (e) =>
                      setError(errorMessage(e instanceof ApiError ? e.code : undefined)),
                  })
                }
              >
                {t('trainer.start')}
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  const ids = targetsOf(item);
  const labelText = (id: string) => {
    const v = answerOf(answers, item, id);
    return v ? t(item.type === 'zone' ? `status.${v}` : `posture.${v}`) : '';
  };
  const labels = Object.fromEntries(
    ids
      .filter((id) => answerOf(answers, item, id))
      .map((id) => [id, { text: labelText(id), tone: `ans-${answerOf(answers, item, id)}` }]),
  );
  const setLabel = (label: string) => {
    if (!selected) return;
    const cur = answers[item.id] ?? { regions: {}, people: {} };
    const next = {
      ...answers,
      [item.id]:
        item.type === 'zone'
          ? { ...cur, regions: { ...cur.regions, [selected]: label } }
          : { ...cur, people: { ...cur.people, [selected]: label } },
    } as Answers;
    setAnswers(next);
    const after = ids.slice(ids.indexOf(selected) + 1).concat(ids.slice(0, ids.indexOf(selected)));
    const nextId = after.find((id) => !answerOf(next, item, id));
    if (nextId) setSelected(nextId);
  };
  const doSubmit = () =>
    submit.mutate(
      { id: attempt.id, answers },
      {
        onSuccess: (a) => {
          try {
            sessionStorage.removeItem(`iv.attempt.${attempt.id}`);
          } catch {
            /* ignore */
          }
          navigate(`/trainer/attempts/${a.id}`, { replace: true });
        },
        onError: (e) => setError(errorMessage(e instanceof ApiError ? e.code : undefined)),
      },
    );

  return (
    <>
      <PageHeader page="trainer" />
      <div className="attempt-head">
        <h2>{pick(sc.title_en, sc.title_ur)}</h2>
        <div
          className="steps"
          aria-label={t('trainer.progress', { n: index + 1, total: items.length })}
        >
          {items.map((it, i) => (
            <button
              key={it.id}
              type="button"
              className={`step${i === index ? ' current' : ''}${targetsOf(it).every((id) => answerOf(answers, it, id)) ? ' done' : ''}`}
              onClick={() => setIndex(i)}
              aria-current={i === index ? 'step' : undefined}
            >
              {i + 1}
            </button>
          ))}
        </div>
      </div>
      <div className="attempt-grid" data-testid="attempt" data-item-type={item.type}>
        <div className="panel">
          <div className="panel-body">
            <MediaStage
              item={item as StageItem}
              labels={labels}
              shapeClass={(id) => (answerOf(answers, item, id) ? 'answered' : 'open')}
              selectedId={selected}
              onSelect={setSelected}
            />
          </div>
        </div>
        <div className="panel attempt-side">
          <div className="panel-body">
            <p className="muted">
              {t(item.type === 'zone' ? 'trainer.howZone' : 'trainer.howPosture')}
            </p>
            <div className="target-chips" role="list">
              {ids.map((id, i) => (
                <button
                  key={id}
                  type="button"
                  role="listitem"
                  className={`target-chip${selected === id ? ' selected' : ''}`}
                  onClick={() => setSelected(id)}
                  aria-pressed={selected === id}
                  data-testid="target-chip"
                  data-target={id}
                >
                  {t(item.type === 'zone' ? 'trainer.region' : 'trainer.person', { n: i + 1 })}
                  <span className="v">{labelText(id) || '—'}</span>
                </button>
              ))}
            </div>
            <LabelPicker
              type={item.type}
              value={selected ? answerOf(answers, item, selected) : undefined}
              disabled={!selected}
              onPick={setLabel}
            />
            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}
            <div className="row-actions">
              <button
                type="button"
                className="btn"
                disabled={index === 0}
                onClick={() => setIndex(index - 1)}
              >
                {t('common.back')}
              </button>
              {index < items.length - 1 ? (
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => setIndex(index + 1)}
                  data-testid="next-item"
                >
                  {t('common.next')}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn primary"
                  disabled={remaining > 0 || submit.isPending}
                  onClick={doSubmit}
                  data-testid="submit-attempt"
                >
                  {t('trainer.submit')}
                </button>
              )}
            </div>
            {remaining > 0 && (
              <p className="muted small">{t('trainer.remaining', { count: remaining })}</p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
