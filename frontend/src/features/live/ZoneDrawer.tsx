import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRenameZone, useZoneHistory } from '../../api/incidents';
import type { ZoneOut } from '../../api/types';
import { StatusChip } from '../../components/StatusChip';
import { formatTime, pct } from '../../lib/format';

export function ZoneDrawer({
  zone,
  incidentId,
  canEdit,
  onClose,
}: {
  zone: ZoneOut;
  incidentId: string;
  canEdit: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const history = useZoneHistory(zone.id);
  const rename = useRenameZone(incidentId);
  const [label, setLabel] = useState(zone.label ?? '');
  useEffect(() => setLabel(zone.label ?? ''), [zone.label]);

  return (
    <aside
      className="drawer"
      role="dialog"
      aria-label={t('live.zoneDrawerTitle', { code: zone.code })}
      data-testid="zone-drawer"
    >
      <div className="drawer-head">
        <h2>{t('live.zoneDrawerTitle', { code: zone.code })}</h2>
        <button
          type="button"
          className="modal-close"
          onClick={onClose}
          aria-label={t('confirm.cancel')}
        >
          ✕
        </button>
      </div>
      <div className="drawer-body">
        <div>
          <StatusChip status={zone.status} />
          {zone.stale && <div className="hint">{t('status.stale')}</div>}
        </div>
        <dl className="kv">
          <dt>{t('live.risk')}</dt>
          <dd>{pct(zone.risk_score)}</dd>
          <dt>{t('live.confidence')}</dt>
          <dd>{pct(zone.confidence)}</dd>
          <dt>{t('live.assignedTo')}</dt>
          <dd>{zone.assignees.map((a) => a.full_name).join(', ') || t('live.nobodyAssigned')}</dd>
          {zone.status_updated_at && (
            <>
              <dt>⏱</dt>
              <dd>{t('live.updatedAt', { time: formatTime(zone.status_updated_at, true) })}</dd>
            </>
          )}
        </dl>
        {canEdit && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              rename.mutate({ zoneId: zone.id, label });
            }}
          >
            <label className="field-label" htmlFor="zone-label">
              {t('live.zoneLabel')}
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                id="zone-label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                maxLength={120}
              />
              <button type="submit" className="btn" disabled={rename.isPending}>
                {rename.isSuccess ? t('common.saved') : t('common.save')}
              </button>
            </div>
          </form>
        )}
        <div>
          <div className="field-label">{t('live.zoneHistory')}</div>
          {history.data?.length ? (
            <ul className="history-list">
              {history.data.map((a) => (
                <li key={a.id}>
                  <span className="when">{formatTime(a.created_at, true)}</span>
                  <StatusChip status={a.status} />
                  <span className="muted">{pct(a.confidence)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t('live.noHistory')}</p>
          )}
        </div>
      </div>
    </aside>
  );
}
