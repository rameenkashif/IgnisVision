import { Fragment, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAudit, useAuditFacets, type AuditOut } from '../../api/admin';
import { PageHeader } from '../../components/PageHeader';
import { formatDateTime } from '../../lib/format';
import { AdminTabs } from './AdminTabs';

/** Before/after of one audit entry, changed fields first. */
function Diff({ row }: { row: AuditOut }) {
  const { t } = useTranslation();
  const before = (row.before ?? {}) as Record<string, unknown>;
  const after = (row.after ?? {}) as Record<string, unknown>;
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
  const show = (v: unknown) =>
    v === undefined ? '—' : typeof v === 'string' ? v : JSON.stringify(v);
  if (!keys.length) return <p className="muted small">{t('admin.audit.noDetail')}</p>;
  return (
    <table className="table diff" dir="ltr">
      <thead>
        <tr>
          <th>{t('admin.audit.field')}</th>
          <th>{t('admin.audit.before')}</th>
          <th>{t('admin.audit.after')}</th>
        </tr>
      </thead>
      <tbody>
        {keys.map((k) => {
          const changed = JSON.stringify(before[k]) !== JSON.stringify(after[k]);
          return (
            <tr key={k} className={changed ? 'changed' : undefined}>
              <td>{k}</td>
              <td>
                <code>{show(before[k])}</code>
              </td>
              <td>
                <code>{show(after[k])}</code>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** Audit log viewer (SRS §5.5.3): filters, paging and per-entry before/after. */
export function AdminAudit() {
  const { t } = useTranslation();
  const facets = useAuditFacets();
  const [f, setF] = useState({ action: '', entity_type: '', from: '', to: '' });
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const q = useAudit({ ...f, offset });
  const total = q.data?.total ?? 0;
  const upd = (k: keyof typeof f, v: string) => {
    setF({ ...f, [k]: v });
    setOffset(0);
  };

  return (
    <>
      <PageHeader page="admin" />
      <AdminTabs />
      <div className="filters" role="search">
        <label>
          <span className="field-label">{t('admin.audit.action')}</span>
          <select
            value={f.action}
            onChange={(e) => upd('action', e.target.value)}
            data-testid="audit-action"
          >
            <option value="">{t('reports.filters.all')}</option>
            {facets.data?.actions.map((a) => (
              <option key={a} value={a}>
                {t(`admin.audit.actions.${a.replace('.', '_')}`, { defaultValue: a })}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">{t('admin.audit.entity')}</span>
          <select value={f.entity_type} onChange={(e) => upd('entity_type', e.target.value)}>
            <option value="">{t('reports.filters.all')}</option>
            {facets.data?.entity_types.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">{t('reports.filters.from')}</span>
          <input type="date" value={f.from} onChange={(e) => upd('from', e.target.value)} />
        </label>
        <label>
          <span className="field-label">{t('reports.filters.to')}</span>
          <input type="date" value={f.to} onChange={(e) => upd('to', e.target.value)} />
        </label>
      </div>
      <div className="panel">
        <div className="panel-body table-wrap">
          <table className="table" data-testid="audit-table">
            <thead>
              <tr>
                <th>{t('reports.time')}</th>
                <th>{t('admin.audit.actor')}</th>
                <th>{t('admin.audit.action')}</th>
                <th>{t('admin.audit.entity')}</th>
                <th>{t('admin.audit.ip')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {q.data?.items.map((r) => (
                <Fragment key={r.id}>
                  <tr data-action={r.action}>
                    <td>{formatDateTime(r.created_at)}</td>
                    <td>
                      {r.actor_name ?? <span className="muted">{t('admin.audit.system')}</span>}
                    </td>
                    <td>
                      {t(`admin.audit.actions.${r.action.replace('.', '_')}`, {
                        defaultValue: r.action,
                      })}
                    </td>
                    <td dir="ltr">
                      {r.entity_type}
                      {r.entity_id && (
                        <span className="muted small"> {r.entity_id.slice(0, 8)}</span>
                      )}
                    </td>
                    <td dir="ltr">{String(r.ip ?? '—')}</td>
                    <td>
                      <button
                        type="button"
                        className="btn"
                        aria-expanded={open === r.id}
                        onClick={() => setOpen(open === r.id ? null : r.id)}
                        data-testid="audit-details"
                      >
                        {open === r.id ? t('admin.audit.hide') : t('admin.audit.details')}
                      </button>
                    </td>
                  </tr>
                  {open === r.id && (
                    <tr className="detail-row">
                      <td colSpan={6}>
                        <Diff row={r} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {q.data?.items.length === 0 && <p className="muted">{t('admin.audit.none')}</p>}
          {total > 50 && (
            <div className="pager">
              <button
                type="button"
                className="btn"
                disabled={offset === 0}
                onClick={() => setOffset(offset - 50)}
              >
                {t('common.back')}
              </button>
              <span className="muted small">
                {offset + 1}–{Math.min(offset + 50, total)} / {total}
              </span>
              <button
                type="button"
                className="btn"
                disabled={offset + 50 >= total}
                onClick={() => setOffset(offset + 50)}
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
