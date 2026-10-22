import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminSettings, useSaveSettings, type SystemSettings } from '../../api/admin';
import { ApiError } from '../../api/errors';
import { PageHeader } from '../../components/PageHeader';
import { errorMessage } from '../../i18n';
import { AdminTabs } from './AdminTabs';
import { SECTIONS, get, path, set, validate, type Section } from './settingsForm';

function SectionForm({ section, saved }: { section: Section; saved: SystemSettings }) {
  const { t } = useTranslation();
  const save = useSaveSettings();
  const [draft, setDraft] = useState(saved);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => setDraft(saved), [saved]);
  const changed = section.keys.filter((k) => JSON.stringify(draft[k]) !== JSON.stringify(saved[k]));
  const errs = validate(draft, section);
  const invalid = Object.keys(errs).length > 0;

  const onSave = () => {
    setMsg(null);
    save.mutate(Object.fromEntries(changed.map((k) => [k, draft[k]])) as Partial<SystemSettings>, {
      onSuccess: () => setMsg({ ok: true, text: t('admin.set.saved') }),
      onError: (e) => {
        const p = e instanceof ApiError ? (e.params as { key?: string; detail?: string }) : {};
        setMsg({
          ok: false,
          text: p.key
            ? `${p.key}: ${p.detail}`
            : errorMessage(e instanceof ApiError ? e.code : undefined),
        });
      },
    });
  };

  return (
    <section className="panel settings-section" data-section={section.id}>
      <div className="panel-head">
        <h2>{t(`admin.set.sec.${section.id}`)}</h2>
      </div>
      <div className="panel-body">
        <p className="muted small">{t(`admin.set.secHint.${section.id}`)}</p>
        <div className="settings-grid">
          {section.fields.map(([k, sub, min, max, step]) => {
            const p = path(k, sub);
            const v = get(draft, k, sub) as number | null;
            const forever = k === 'retention_days' && v === null;
            return (
              <label key={p} className={errs[p] ? 'has-error' : undefined}>
                <span className="field-label">{t(`admin.set.f.${p}`)}</span>
                {k === 'retention_days' && (
                  <span className="check">
                    <input
                      type="checkbox"
                      checked={forever}
                      onChange={(e) => setDraft(set(draft, k, sub, e.target.checked ? null : 365))}
                    />
                    {t('admin.set.keepForever')}
                  </span>
                )}
                {!forever && (
                  <input
                    type="number"
                    min={min}
                    max={max}
                    step={step}
                    value={v == null || Number.isNaN(v) ? '' : v}
                    data-field={p}
                    aria-invalid={!!errs[p]}
                    onChange={(e) =>
                      setDraft(
                        set(draft, k, sub, e.target.value === '' ? NaN : Number(e.target.value)),
                      )
                    }
                  />
                )}
                <span className={errs[p] ? 'error-text small' : 'hint'}>
                  {errs[p] ? t(errs[p], { min, max }) : t('admin.set.range', { min, max })}
                </span>
              </label>
            );
          })}
          {section.toggles?.map(([k, sub]) => (
            <label key={path(k, sub)} className="check toggle">
              <input
                type="checkbox"
                checked={!!get(draft, k, sub)}
                data-field={path(k, sub)}
                onChange={(e) => setDraft(set(draft, k, sub, e.target.checked))}
              />
              <span>
                {t(`admin.set.f.${path(k, sub)}`)}
                <span className="hint">{t(`admin.set.h.${path(k, sub)}`)}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="row-actions">
          <button
            type="button"
            className="btn"
            disabled={!changed.length}
            onClick={() => setDraft(saved)}
          >
            {t('admin.set.revert')}
          </button>
          <button
            type="button"
            className="btn primary"
            disabled={!changed.length || invalid || save.isPending}
            onClick={onSave}
            data-testid={`save-${section.id}`}
          >
            {t('common.save')}
          </button>
          {msg && (
            <span className={msg.ok ? 'ok-text small' : 'error-text small'} role="status">
              {msg.text}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

/** System settings editor (HANDOFF §13 Phase 8): RPI, fusion and thresholds, validated. */
export function AdminSettings() {
  const { t } = useTranslation();
  const q = useAdminSettings();
  return (
    <>
      <PageHeader page="admin" />
      <AdminTabs />
      <p className="banner warn">{t('admin.set.tuneNote')}</p>
      {q.data ? (
        SECTIONS.map((s) => <SectionForm key={s.id} section={s} saved={q.data} />)
      ) : (
        <div className="loader">{t('common.loading')}</div>
      )}
    </>
  );
}
