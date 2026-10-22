import { useTranslation } from 'react-i18next';
import type { AlertOut } from '../api/types';
import { alertText } from '../lib/alerts';
import { formatTime } from '../lib/format';

export function AlertFeed({
  alerts,
  onSelect,
  onAck,
  canAck,
}: {
  alerts: AlertOut[];
  onSelect?: (a: AlertOut) => void;
  onAck?: (a: AlertOut) => void;
  canAck?: boolean;
}) {
  const { t } = useTranslation();
  if (!alerts.length) return <p className="muted">{t('live.noAlerts')}</p>;
  return (
    <ul className="alerts-col" aria-live="polite" data-testid="alert-feed">
      {alerts.map((a) => (
        <li key={a.id} className={`alert ${a.severity}${a.acknowledged_at ? ' acked' : ''}`}>
          <button type="button" className="alert-main" onClick={() => onSelect?.(a)}>
            <span className="sev">{a.severity.toUpperCase()}</span>
            <span className="txt">
              <p>{alertText(t, a)}</p>
              <span>{formatTime(a.created_at)}</span>
            </span>
          </button>
          {canAck && !a.acknowledged_at && (
            <button type="button" className="btn ack" onClick={() => onAck?.(a)}>
              {t('live.acknowledge')}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
