import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError } from '../../api/errors';
import { useAdminScenarios, useCreateScenario, type ScenarioIn } from '../../api/training';
import { Modal } from '../../components/Modal';
import { PageHeader } from '../../components/PageHeader';
import { errorMessage } from '../../i18n';
import { pick } from '../trainer/util';
import { AdminTabs } from './AdminTabs';
import { ScenarioFields } from './ScenarioFields';

const EMPTY_SCENARIO: ScenarioIn = {
  title_en: '',
  title_ur: '',
  description_en: '',
  description_ur: '',
  difficulty: 1,
  kind: 'zone',
  is_active: true,
};

export function AdminScenarios() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const list = useAdminScenarios();
  const create = useCreateScenario();
  const [draft, setDraft] = useState<ScenarioIn | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      <PageHeader
        page="admin"
        actions={
          <button
            type="button"
            className="btn primary"
            onClick={() => setDraft(EMPTY_SCENARIO)}
            data-testid="new-scenario"
          >
            + {t('admin.sc.new')}
          </button>
        }
      />
      <AdminTabs />
      <div className="panel">
        <div className="panel-body table-wrap">
          <table className="table" data-testid="admin-scenarios">
            <thead>
              <tr>
                <th>{t('trainer.scenario')}</th>
                <th>{t('admin.sc.kind')}</th>
                <th>{t('admin.sc.items')}</th>
                <th>{t('admin.sc.status')}</th>
              </tr>
            </thead>
            <tbody>
              {list.data?.map((s) => (
                <tr key={s.id} data-scenario={s.title_en}>
                  <td>
                    <Link to={`/admin/scenarios/${s.id}`}>{pick(s.title_en, s.title_ur)}</Link>
                    {s.is_placeholder && (
                      <span className="tag warn">{t('trainer.placeholder')}</span>
                    )}
                  </td>
                  <td>{t(`trainer.kind.${s.kind}`)}</td>
                  <td>{t('admin.sc.usableOf', { usable: s.usable_count, total: s.item_count })}</td>
                  <td>{s.is_active ? t('admin.sc.active') : t('admin.sc.inactive')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.data?.length === 0 && <p className="muted">{t('trainer.noScenarios')}</p>}
        </div>
      </div>
      {draft && (
        <Modal
          title={t('admin.sc.new')}
          onClose={() => setDraft(null)}
          wide
          footer={
            <>
              {error && <span className="error-text">{error}</span>}
              <button type="button" className="btn" onClick={() => setDraft(null)}>
                {t('common.cancel')}
              </button>
              <button
                type="button"
                className="btn primary"
                disabled={!draft.title_en || !draft.title_ur || create.isPending}
                data-testid="create-scenario"
                onClick={() =>
                  create.mutate(draft, {
                    onSuccess: (sc) => navigate(`/admin/scenarios/${sc.id}`),
                    onError: (e) =>
                      setError(errorMessage(e instanceof ApiError ? e.code : undefined)),
                  })
                }
              >
                {t('common.save')}
              </button>
            </>
          }
        >
          <ScenarioFields value={draft} onChange={setDraft} />
        </Modal>
      )}
    </>
  );
}
