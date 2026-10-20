import { useTranslation } from 'react-i18next';
import type { IncidentDetail } from '../api/types';
import { pct } from '../lib/format';

export function KpiStrip({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const k = incident.kpis;
  const statusCls = ['safe', 'caution', 'unsafe', 'blocked'].includes(k.building_status)
    ? k.building_status
    : '';
  return (
    <div className="kpi-strip" data-testid="kpi-strip">
      <div className="kpi">
        <div className="lbl">{t('kpi.incident')}</div>
        <div className="val">{incident.code}</div>
        <div className="sub">{incident.address}</div>
      </div>
      <div className="kpi">
        <div className="lbl">{t('kpi.victims')}</div>
        <div className="val" style={{ color: 'var(--thermal)' }}>
          {k.victims_detected}
        </div>
        <div className="sub">{t('kpi.victimsSub')}</div>
      </div>
      <div className="kpi">
        <div className="lbl">{t('kpi.building')}</div>
        <div className={`val ${statusCls}`}>{t(`status.${k.building_status}`)}</div>
        <div className="sub">
          {k.classified ? t('live.zoneCount', { count: k.classified }) : t('kpi.awaiting')}
        </div>
      </div>
      <div className="kpi">
        <div className="lbl">{t('kpi.units')}</div>
        <div className="val">{k.response_units}</div>
        <div className="sub">{t('kpi.unitsSub')}</div>
      </div>
      <div className="kpi">
        <div className="lbl">{t('kpi.ai')}</div>
        <div className="val">{pct(k.ai_confidence)}</div>
        <div className="sub">{t('kpi.aiSub')}</div>
      </div>
    </div>
  );
}
