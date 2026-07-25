import { useEffect, useMemo, useState } from 'react';
import { useIncident } from '../../state/IncidentContext';
import { DispatchModal } from './DispatchModal';
import './LiveMonitoring.css';

const COLS = 8;

function formatClock(d: Date) {
  let h = d.getHours();
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${h}:${m}:${s} ${ampm}`;
}

export function LiveMonitoring() {
  const { incident, stage, alerts, activeCam, setActiveCam, goLive } = useIncident();
  const [modalOpen, setModalOpen] = useState(false);
  const [clock, setClock] = useState(() => formatClock(new Date()));

  useEffect(() => {
    const t = setInterval(() => setClock(formatClock(new Date())), 1000);
    return () => clearInterval(t);
  }, []);

  const donut = useMemo(() => {
    if (!incident || incident.zones.length === 0) return { safePct: 0, cautionPct: 0, unsafePct: 0 };
    const total = incident.zones.length;
    const counts = { safe: 0, caution: 0, unsafe: 0, neutral: 0 };
    incident.zones.forEach((z) => counts[z.status]++);
    const safePct = Math.round((counts.safe / total) * 100);
    const cautionPct = Math.round((counts.caution / total) * 100);
    const unsafePct = 100 - safePct - cautionPct;
    return { safePct, cautionPct, unsafePct };
  }, [incident]);

  const evacOkPct = useMemo(() => {
    if (!incident || incident.zones.length === 0) return 100;
    const total = incident.zones.length;
    let safeN = 0;
    let cautionN = 0;
    incident.zones.forEach((z) => {
      if (z.status === 'safe') safeN++;
      if (z.status === 'caution') cautionN++;
    });
    return Math.round(((safeN + cautionN) / total) * 100);
  }, [incident]);

  const victims = useMemo(() => incident?.zones.filter((z) => z.hasVictim) ?? [], [incident]);

  const aiConf = useMemo(() => {
    if (stage !== 'live') return '—';
    return `${88 + Math.floor(Math.random() * 8)}%`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident, stage]);

  const okPct = donut.safePct + donut.cautionPct;
  const buildingStatus = stage === 'briefing' ? 'Assessing' : okPct < 40 ? 'High risk' : okPct < 70 ? 'Elevated' : 'Stable';
  const buildingStatusClass = stage === 'briefing' ? '' : okPct < 40 ? 'unsafe' : okPct < 70 ? 'caution' : 'safe';
  const buildingStatusSub = stage === 'briefing' ? 'Awaiting camera feed' : okPct < 40 ? 'Structural instability' : 'Monitoring';

  const crit = alerts[0]?.level === 'crit';
  const camsWithCrit = new Set(alerts.filter((a) => a.level === 'crit').map((a) => a.cam));
  const cams = incident ? [...new Set(incident.teams.map((t) => t.cam))].sort((a, b) => a - b) : [];
  const activeTeam = incident?.teams.find((t) => t.cam === activeCam) ?? incident?.teams[0];
  const activeZone = incident?.zones.find((z) => z.id === activeTeam?.zone);

  function findCamForZone(zoneId: string) {
    return incident?.teams.find((t) => t.zone === zoneId)?.cam ?? activeCam;
  }

  return (
    <div className="page-live">
      <div className={'topbar' + (crit ? ' crit' : '')}>
        {crit && (
          <div className="top-alert">
            <span className="dot" />
            <span>
              {alerts[0].text} — Camera {alerts[0].cam}
            </span>
          </div>
        )}
        <div className="top-right">
          <span className="clock">{clock}</span>
          <div className="commander-chip">
            <div className="avatar">RI</div>
            <div>
              <div className="name">Rimsha Irfan</div>
              <div className="role">Karachi Fire Dept.</div>
            </div>
          </div>
        </div>
      </div>

      {incident && (
        <div className="kpi-strip">
          <div className="kpi">
            <div className="lbl">Active incident</div>
            <div className="val">{incident.id}</div>
            <div className="sub">{incident.location}</div>
          </div>
          <div className="kpi">
            <div className="lbl">Victims detected</div>
            <div className="val" style={{ color: 'var(--thermal)' }}>
              {victims.length}
            </div>
            <div className="sub">This incident</div>
          </div>
          <div className="kpi">
            <div className="lbl">Building status</div>
            <div className={'val' + (buildingStatusClass ? ' ' + buildingStatusClass : '')}>{buildingStatus}</div>
            <div className="sub">{buildingStatusSub}</div>
          </div>
          <div className="kpi">
            <div className="lbl">Response units</div>
            <div className="val">{incident.teams.length}</div>
            <div className="sub">On site</div>
          </div>
          <div className="kpi">
            <div className="lbl">AI confidence</div>
            <div className="val">{aiConf}</div>
            <div className="sub">Model average</div>
          </div>
        </div>
      )}

      {stage === 'empty' && (
        <div className="empty-state">
          <div className="ic-circle">⚠</div>
          <h2>No active emergency</h2>
          <p>
            The console is idle. When a call comes in and a team is dispatched, log the emergency to start structural
            mapping and zone assignment.
          </p>
          <button className="plus-btn" onClick={() => setModalOpen(true)}>
            +
          </button>
          <div className="plus-label">Log new emergency</div>
        </div>
      )}

      {stage === 'briefing' && incident && (
        <div>
          <div className="briefing-banner">
            <div>
              <div className="t">Teams dispatched — zones assigned, awaiting camera feed</div>
              <div className="s">
                {incident.teams.length} teams en route · {incident.zones.length} zones mapped · {incident.structType} structure
              </div>
            </div>
            <button className="btn primary" onClick={goLive}>
              Cameras online — start monitoring
            </button>
          </div>
          <div className="panel">
            <div className="panel-head">
              <h2>{incident.location} — structural map</h2>
              <span style={{ fontSize: 10, color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}>
                {incident.zones.length} zones
              </span>
            </div>
            <div className="panel-body">
              <div className="zonemap-legend">
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: 'var(--bg-3)' }} />
                  Assigned — not yet live
                </div>
              </div>
              <div className="zone-grid" style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)` }}>
                {incident.zones.map((z) => {
                  const assigned = incident.teams.find((t) => t.zone === z.id);
                  return (
                    <div className="zone-cell neutral" key={z.id}>
                      <span className="zid">{z.id}</span>
                      {assigned && (
                        <span className="assignee">
                          {assigned.name} · Cam {assigned.cam}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {stage === 'live' && incident && activeTeam && activeZone && (
        <div>
          <div className="cam-tabs">
            {cams.map((c) => (
              <button
                key={c}
                className={(c === activeCam ? 'active ' : '') + (camsWithCrit.has(c) && c !== activeCam ? 'flag-on' : '')}
                onClick={() => setActiveCam(c)}
              >
                Camera {c}
                <span className="flag" />
              </button>
            ))}
          </div>

          <div className="live-grid">
            <div className="panel">
              <div className="panel-head">
                <h2>Thermal camera</h2>
                <span className="mono-dim">
                  CAM {activeCam} · {activeTeam.name}
                </span>
              </div>
              <div className="panel-body">
                <div className="cam-feed thermal">
                  <div className="frame-label">ZONE {activeZone.id}</div>
                  <div className="rec-badge">
                    <span className="rec-dot" />
                    LIVE
                  </div>
                  <div className="temp-tag">
                    {activeZone.hasVictim ? `37.${activeZone.tempDecimal ?? 0}°C human signature` : `Ambient ${activeZone.ambientTemp ?? 28}°C`}
                  </div>
                  {activeZone.hasVictim && (
                    <div
                      className="victim-box"
                      style={{ top: '38%', left: '48%' }}
                      data-label={`HUMAN ${activeZone.conf ?? 90}%`}
                    />
                  )}
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>RGB camera</h2>
                <span className="mono-dim">
                  CAM {activeCam} · {activeTeam.name}
                </span>
              </div>
              <div className="panel-body">
                <div className="cam-feed rgb">
                  <div className="rgb-zone-overlay">
                    <div
                      className="rz"
                      style={{
                        inset: 0,
                        background: `var(--${activeZone.status === 'neutral' ? 'bg-3' : activeZone.status})`,
                      }}
                    />
                  </div>
                  <div className="frame-label">ZONE {activeZone.id}</div>
                  <div className="rec-badge">
                    <span className="rec-dot" />
                    LIVE
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>Structural map</h2>
                <span className="mono-dim">Live fusion</span>
              </div>
              <div className="panel-body">
                <div className="zonemap-legend">
                  <div className="legend-item">
                    <span className="legend-swatch" style={{ background: 'var(--safe)' }} />
                    Safe
                  </div>
                  <div className="legend-item">
                    <span className="legend-swatch" style={{ background: 'var(--caution)' }} />
                    Caution
                  </div>
                  <div className="legend-item">
                    <span className="legend-swatch" style={{ background: 'var(--unsafe)' }} />
                    Unsafe
                  </div>
                  <div className="legend-item">
                    <span className="legend-swatch" style={{ background: 'var(--thermal)' }} />
                    Human
                  </div>
                </div>
                <div className="zone-grid" style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)` }}>
                  {incident.zones.map((z) => {
                    const assigned = incident.teams.find((t) => t.zone === z.id);
                    return (
                      <div className={'zone-cell ' + z.status + (z.hasVictim ? ' victim' : '')} key={z.id}>
                        <span className="zid">{z.id}</span>
                        {assigned && <span className="assignee">{assigned.name}</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>Real-time alerts</h2>
                <span className="mono-dim">{alerts.length}</span>
              </div>
              <div className="panel-body">
                <div className="alerts-col">
                  {alerts.length === 0 && <div style={{ fontSize: 11, color: 'var(--text-low)' }}>No alerts yet.</div>}
                  {alerts.map((a) => (
                    <div className={'alert ' + a.level} key={a.id} onClick={() => setActiveCam(a.cam)}>
                      <div className="txt">
                        <p>{a.text}</p>
                        <span>{a.time}</span>
                        <br />
                        <span className="cam-src">
                          Camera {a.cam}
                          {a.cam !== activeCam ? ' — jump to feed' : ' — this feed'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="bottom-grid">
            <div className="panel">
              <div className="panel-head">
                <h2>Humans detected</h2>
                <span className="mono-dim">{victims.length} active</span>
              </div>
              <div className="panel-body">
                <div className="humans-list">
                  {victims.length === 0 && <div style={{ fontSize: 11, color: 'var(--text-low)' }}>No humans detected yet.</div>}
                  {victims.map((z, i) => (
                    <div className="human-card" key={z.id}>
                      <div className="badge">V{i + 1}</div>
                      <div className="d">
                        <div className="z">Zone {z.id}</div>
                        <div className="c">Thermal confirmed · Cam {findCamForZone(z.id)}</div>
                      </div>
                      <div className="conf">{z.conf}%</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>Zone classification</h2>
              </div>
              <div className="panel-body">
                <div className="donut-wrap">
                  <svg width="100" height="100" viewBox="0 0 42 42">
                    <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="#1D242B" strokeWidth="6" />
                    <circle
                      cx="21"
                      cy="21"
                      r="15.9"
                      fill="transparent"
                      stroke="#2FA66E"
                      strokeWidth="6"
                      strokeDasharray={`${donut.safePct} ${100 - donut.safePct}`}
                      strokeDashoffset={25}
                      transform="rotate(-90 21 21)"
                    />
                    <circle
                      cx="21"
                      cy="21"
                      r="15.9"
                      fill="transparent"
                      stroke="#E8A93B"
                      strokeWidth="6"
                      strokeDasharray={`${donut.cautionPct} ${100 - donut.cautionPct}`}
                      strokeDashoffset={25 - donut.safePct}
                      transform="rotate(-90 21 21)"
                    />
                    <circle
                      cx="21"
                      cy="21"
                      r="15.9"
                      fill="transparent"
                      stroke="#DD4A32"
                      strokeWidth="6"
                      strokeDasharray={`${donut.unsafePct} ${100 - donut.unsafePct}`}
                      strokeDashoffset={25 - donut.safePct - donut.cautionPct}
                      transform="rotate(-90 21 21)"
                    />
                  </svg>
                  <div className="donut-legend">
                    <div className="row">
                      <span className="sw" style={{ background: 'var(--safe)' }} />
                      Safe<span className="pct">{donut.safePct}%</span>
                    </div>
                    <div className="row">
                      <span className="sw" style={{ background: 'var(--caution)' }} />
                      Caution<span className="pct">{donut.cautionPct}%</span>
                    </div>
                    <div className="row">
                      <span className="sw" style={{ background: 'var(--unsafe)' }} />
                      Unsafe<span className="pct">{donut.unsafePct}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>Building safety threshold</h2>
              </div>
              <div className="panel-body">
                <div className={'evac-bar ' + (evacOkPct < 40 ? 'warn' : 'ok')}>
                  <div className="ic">{evacOkPct < 40 ? '⚠' : '✓'}</div>
                  <div>
                    <div className="t">
                      {evacOkPct < 40 ? 'Evacuate — building below safe threshold' : 'Building within safe operating threshold'}
                    </div>
                    <div className="s">
                      {evacOkPct < 40
                        ? `Safe + caution zones at ${evacOkPct}%. Recommend all teams withdraw immediately.`
                        : `Safe + caution zones above ${evacOkPct}% — teams may continue operations.`}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <DispatchModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
