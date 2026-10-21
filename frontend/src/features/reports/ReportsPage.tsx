import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useIncidentSearch } from '../../api/reports';
import { PageHeader } from '../../components/PageHeader';
import { formatDateTime } from '../../lib/format';

type Status = 'draft' | 'dispatched' | 'active' | 'closed';

/** Incident records (HANDOFF §11): list with filters; closed incidents open their report. */
export function ReportsPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<'closed' | 'all' | 'open'>('closed');
  const [q, setQ] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const statuses: Status[] | undefined =
    status === 'closed' ? ['closed'] : status === 'open' ? ['dispatched', 'active'] : undefined;
  const list = useIncidentSearch({ status: statuses, q, from, to });

  return (
    <>
      <PageHeader page="reports" />
      <div className="filters" role="search">
        <label>
          <span className="field-label">{t('reports.filters.status')}</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as typeof status)}
            data-testid="reports-status"
          >
            <option value="closed">{t('incidentStatus.closed')}</option>
            <option value="open">
              {t('incidentStatus.active')} / {t('incidentStatus.dispatched')}
            </option>
            <option value="all">{t('reports.filters.all')}</option>
          </select>
        </label>
        <label className="grow">
          <span className="field-label">{t('reports.filters.search')}</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            data-testid="reports-search"
          />
        </label>
        <label>
          <span className="field-label">{t('reports.filters.from')}</span>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label>
          <span className="field-label">{t('reports.filters.to')}</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
      </div>
      <div className="panel">
        <div className="panel-body table-wrap">
          {list.data && list.data.items.length === 0 ? (
            <p className="muted">{t('reports.none')}</p>
          ) : (
            <table className="table" data-testid="reports-table">
              <thead>
                <tr>
                  <th>{t('reports.cols.code')}</th>
                  <th>{t('reports.cols.address')}</th>
                  <th>{t('reports.cols.status')}</th>
                  <th>{t('reports.cols.opened')}</th>
                  <th>{t('reports.cols.closed')}</th>
                  <th>{t('reports.cols.source')}</th>
                </tr>
              </thead>
              <tbody>
                {list.data?.items.map((i) => (
                  <tr key={i.id} data-code={i.code}>
                    <td>
                      <Link
                        to={i.status === 'closed' ? `/reports/${i.id}` : `/live?incident=${i.id}`}
                        dir="ltr"
                      >
                        {i.code}
                      </Link>
                    </td>
                    <td>{i.address ?? '—'}</td>
                    <td>{t(`incidentStatus.${i.status}`)}</td>
                    <td>{formatDateTime(i.opened_at)}</td>
                    <td>{formatDateTime(i.closed_at)}</td>
                    <td>{t(`reports.sourceIncident.${i.source}`, { defaultValue: i.source })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
