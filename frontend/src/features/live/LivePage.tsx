import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import {
  OPEN,
  useAckAlert,
  useActivateIncident,
  useAlerts,
  useCloseIncident,
  useIncident,
  useIncidents,
} from '../../api/incidents';
import type { AlertOut, IncidentDetail, ZoneOut } from '../../api/types';
import { AlertFeed } from '../../components/AlertFeed';
import { Donut, EvacBar } from '../../components/Charts';
import { KpiStrip } from '../../components/KpiStrip';
import { ConfirmDialog } from '../../components/Modal';
import { PageHeader } from '../../components/PageHeader';
import { ZoneGrid, ZoneLegend } from '../../components/ZoneGrid';
import { alertText } from '../../lib/alerts';
import { formatTime } from '../../lib/format';
import { initials } from '../../lib/nav';
import { useAuth } from '../../stores/auth';
import { useUi } from '../../stores/ui';
import { useIncidentStream, useStationStream } from '../../ws/hooks';
import { DispatchModal } from './DispatchModal';
import { ZoneDrawer } from './ZoneDrawer';

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return <span className="clock">{formatTime(now, true)}</span>;
}

/** Live monitoring: empty → briefing (dispatched) → live (active), driven by incident status. */
export function LivePage() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const isCommander = user.role === 'incident_commander';
  const [params, setParams] = useSearchParams();
  const [dispatchOpen, setDispatchOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  useStationStream(true);

  const open = useIncidents(OPEN);
  const openItems = open.data?.items ?? [];
  const selectedId = params.get('incident') ?? openItems[0]?.id;
  const incident = useIncident(openItems.some((i) => i.id === selectedId) ? selectedId : undefined);
  const lastUpdate = useIncidentStream(incident.data?.id);
  const link = useUi((s) => s.link);

  const select = (id: string) => setParams({ incident: id }, { replace: true });

  let body;
  if (open.isLoading) {
    body = (
      <div className="loader" style={{ minHeight: 200 }}>
        {t('common.loading')}
      </div>
    );
  } else if (!openItems.length || !incident.data) {
    body = (
      <div className="empty-state" data-testid="live-empty">
        <div className="ic-circle" aria-hidden="true">
          ⚠
        </div>
        <h2>{t('live.emptyTitle')}</h2>
        <p>{isCommander ? t('live.emptyBody') : t('live.emptyBodyReadOnly')}</p>
        {isCommander && (
          <>
            <button
              type="button"
              className="plus-btn"
              onClick={() => setDispatchOpen(true)}
              aria-label={t('live.logEmergency')}
              data-testid="open-dispatch"
            >
              +
            </button>
            <div className="plus-label">{t('live.logEmergency')}</div>
          </>
        )}
      </div>
    );
  } else if (incident.data.status === 'active') {
    body = (
      <LiveView
        incident={incident.data}
        canAct={isCommander}
        onClosed={(code) => setNotice(t('live.closed', { code }))}
      />
    );
  } else {
    body = <Briefing incident={incident.data} canAct={isCommander} />;
  }

  return (
    <>
      <PageHeader
        page="live"
        actions={
          isCommander && openItems.length > 0 ? (
            <button
              type="button"
              className="btn primary"
              onClick={() => setDispatchOpen(true)}
              data-testid="open-dispatch"
            >
              + {t('live.logEmergency')}
            </button>
          ) : undefined
        }
      />
      {notice && (
        <div className="banner warn" role="status">
          <span>{notice}</span>
          <button type="button" className="btn" onClick={() => setNotice(null)}>
            ✕
          </button>
        </div>
      )}
      {link === 'lost' && incident.data && (
        <div className="banner bad" role="alert" data-testid="connection-lost">
          {t('live.connectionLost', {
            time: formatTime(
              lastUpdate ?? (incident.dataUpdatedAt ? new Date(incident.dataUpdatedAt) : null),
            ),
          })}
        </div>
      )}
      {openItems.length > 1 && (
        <div className="incident-tabs" role="group" aria-label={t('live.selectIncident')}>
          {openItems.map((i) => (
            <button
              key={i.id}
              type="button"
              aria-pressed={i.id === incident.data?.id}
              onClick={() => select(i.id)}
            >
              {i.code} · {t(`incidentStatus.${i.status}`)}
            </button>
          ))}
        </div>
      )}
      {body}
      {dispatchOpen && (
        <DispatchModal
          onClose={() => setDispatchOpen(false)}
          onCreated={(inc) => {
            setDispatchOpen(false);
            select(inc.id);
          }}
        />
      )}
    </>
  );
}

function Briefing({ incident, canAct }: { incident: IncidentDetail; canAct: boolean }) {
  const { t } = useTranslation();
  const activate = useActivateIncident();
  return (
    <div data-testid="live-briefing">
      <div className="briefing-banner">
        <div>
          <div className="t">{t('live.briefingTitle')}</div>
          <div className="s">
            {incident.code} · {incident.address} —{' '}
            {t('live.briefingSub', {
              count: incident.kpis.response_units,
              zones: incident.kpis.zones_total,
            })}
          </div>
        </div>
        {canAct && (
          <button
            type="button"
            className="btn primary"
            onClick={() => activate.mutate(incident.id)}
            disabled={activate.isPending}
            data-testid="go-live"
          >
            {t('live.goLive')}
          </button>
        )}
      </div>
      <div className="panel">
        <div className="panel-head">
          <h2>{t('live.sectorMap')}</h2>
          <span className="meta">{t('live.zoneCount', { count: incident.kpis.zones_total })}</span>
        </div>
        <div className="panel-body">
          <ZoneLegend mode="briefing" />
          <ZoneGrid zones={incident.zones} mode="briefing" />
        </div>
      </div>
    </div>
  );
}

function LiveView({
  incident,
  canAct,
  onClosed,
}: {
  incident: IncidentDetail;
  canAct: boolean;
  onClosed: (code: string) => void;
}) {
  const { t } = useTranslation();
  const alerts = useAlerts(incident.id);
  const ack = useAckAlert(incident.id);
  const close = useCloseIncident();
  const setKeepAlive = useUi((s) => s.setKeepAlive);
  const [zoneId, setZoneId] = useState<string | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);

  // Active incident on screen: keep the session alive (idle exemption, SRS §5.3.1).
  useEffect(() => {
    setKeepAlive(true);
    return () => setKeepAlive(false);
  }, [setKeepAlive]);

  const items = useMemo(() => alerts.data?.items ?? [], [alerts.data]);
  const topCrit = items.find((a) => a.severity === 'crit' && !a.acknowledged_at);
  const zone = incident.zones.find((z) => z.id === zoneId) ?? null;
  const openZone = (z: ZoneOut) => setZoneId(z.id);
  const onAlert = (a: AlertOut) => a.zone_id && setZoneId(a.zone_id);

  return (
    <div data-testid="live-active">
      <div className={`topbar${topCrit ? ' crit' : ''}`} data-testid="topbar">
        {topCrit && (
          <div className="top-alert" role="alert">
            <span className="dot" />
            <span>{alertText(t, topCrit)}</span>
          </div>
        )}
        <div className="top-right">
          <Clock />
          {incident.commander && (
            <div className="commander-chip">
              <div className="avatar">{initials(incident.commander.full_name)}</div>
              <div>
                <div className="name">{incident.commander.full_name}</div>
                <div className="role">{t('app.org')}</div>
              </div>
            </div>
          )}
          {canAct && (
            <button
              type="button"
              className="btn danger"
              onClick={() => setConfirmClose(true)}
              data-testid="close-incident"
            >
              {t('live.closeIncident')}
            </button>
          )}
        </div>
      </div>

      <KpiStrip incident={incident} />

      <div className="live-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>{t('live.thermal')}</h2>
          </div>
          <div className="panel-body">
            <div className="feed-placeholder">{t('live.noThermal')}</div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>{t('live.rgb')}</h2>
          </div>
          <div className="panel-body">
            <div className="feed-placeholder">{t('live.noRgb')}</div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>{t('live.structuralMap')}</h2>
            <span className="meta">{t('live.liveFusion')}</span>
          </div>
          <div className="panel-body">
            <ZoneLegend />
            <ZoneGrid zones={incident.zones} onSelect={openZone} selectedId={zoneId} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>{t('live.alerts')}</h2>
            <span className="meta">{alerts.data?.total ?? 0}</span>
          </div>
          <div className="panel-body">
            <AlertFeed
              alerts={items}
              onSelect={onAlert}
              canAck={canAct}
              onAck={(a) => ack.mutate(a.id)}
            />
          </div>
        </div>
      </div>

      <div className="bottom-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>{t('live.humans')}</h2>
            <span className="meta">{incident.kpis.victims_detected}</span>
          </div>
          <div className="panel-body">
            <p className="muted">{t('live.noHumans')}</p>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>{t('live.zoneClassification')}</h2>
          </div>
          <div className="panel-body">
            <Donut kpis={incident.kpis} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>{t('live.safetyThreshold')}</h2>
          </div>
          <div className="panel-body">
            <EvacBar kpis={incident.kpis} />
          </div>
        </div>
      </div>

      {zone && (
        <ZoneDrawer
          zone={zone}
          incidentId={incident.id}
          canEdit={canAct}
          onClose={() => setZoneId(null)}
        />
      )}
      {confirmClose && (
        <ConfirmDialog
          title={t('live.closeTitle', { code: incident.code })}
          body={t('live.closeBody')}
          confirmLabel={t('live.closeIncident')}
          busy={close.isPending}
          onCancel={() => setConfirmClose(false)}
          onConfirm={() =>
            close.mutate(incident.id, {
              onSuccess: (inc) => {
                setConfirmClose(false);
                onClosed(inc.code);
              },
            })
          }
        />
      )}
    </div>
  );
}
