import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

export type ZoneStatus = 'neutral' | 'safe' | 'caution' | 'unsafe';

export interface Zone {
  id: string;
  label: string;
  floor: number;
  status: ZoneStatus;
  hasVictim?: boolean;
  conf?: number;
  tempDecimal?: number;
  ambientTemp?: number;
}

export interface Team {
  name: string;
  zone: string;
  cam: number;
}

export interface Incident {
  id: string;
  location: string;
  city: string;
  structType: string;
  incidentType: string;
  reportedBy: string;
  zones: Zone[];
  teams: Team[];
}

export type Stage = 'empty' | 'briefing' | 'live';

export type AlertLevel = 'crit' | 'warn' | 'info';

export interface AlertItem {
  id: number;
  level: AlertLevel;
  text: string;
  cam: number;
  time: string;
}

export interface DispatchZoneDraft {
  id: string;
  label: string;
  floor: number;
}

export interface DispatchTeamDraft {
  name: string;
  zone: string;
  cam: number;
}

export interface DispatchInput {
  location: string;
  city: string;
  structType: string;
  incidentType: string;
  reportedBy: string;
  zones: DispatchZoneDraft[];
  teams: DispatchTeamDraft[];
}

function nowTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function findCam(incident: Incident, zoneId: string, fallback: number) {
  return incident.teams.find((t) => t.zone === zoneId)?.cam ?? fallback;
}

let alertSeq = 0;

interface IncidentContextValue {
  incident: Incident | null;
  stage: Stage;
  alerts: AlertItem[];
  activeCam: number;
  setActiveCam: (cam: number) => void;
  createIncident: (input: DispatchInput) => void;
  goLive: () => void;
}

const IncidentContext = createContext<IncidentContextValue | null>(null);

export function IncidentProvider({ children }: { children: ReactNode }) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [stage, setStage] = useState<Stage>('empty');
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [activeCam, setActiveCam] = useState(1);

  const incidentRef = useRef(incident);
  useEffect(() => {
    incidentRef.current = incident;
  }, [incident]);

  function createIncident(input: DispatchInput) {
    const newIncident: Incident = {
      id: 'IGN-2026-' + Math.floor(1000 + Math.random() * 8999),
      location: input.location,
      city: input.city,
      structType: input.structType,
      incidentType: input.incidentType,
      reportedBy: input.reportedBy,
      zones: input.zones.map((z) => ({ ...z, status: 'neutral' })),
      teams: input.teams,
    };
    setIncident(newIncident);
    setAlerts([]);
    setActiveCam(newIncident.teams[0]?.cam ?? 1);
    setStage('briefing');
  }

  function goLive() {
    setStage('live');
  }

  useEffect(() => {
    if (stage !== 'live') return;

    function tick() {
      const prev = incidentRef.current;
      if (!prev || prev.zones.length === 0) return;

      const idx = Math.floor(Math.random() * prev.zones.length);
      const zones = [...prev.zones];
      const z = { ...zones[idx] };
      const roll = Math.random();
      let alert: Omit<AlertItem, 'id'> | null = null;

      if (roll < 0.35) {
        const order: ZoneStatus[] = ['safe', 'caution', 'unsafe'];
        let cur = order.indexOf(z.status === 'neutral' ? 'safe' : z.status);
        if (Math.random() < 0.6 && cur < 2) cur++;
        else if (cur > 0) cur--;
        z.status = order[cur];
      } else if (roll < 0.45 && !z.hasVictim) {
        z.hasVictim = true;
        z.conf = 85 + Math.floor(Math.random() * 14);
        z.tempDecimal = Math.floor(Math.random() * 9);
        alert = { level: 'crit', text: `Human detected — Zone ${z.id}`, cam: findCam(prev, z.id, activeCam), time: nowTime() };
      } else {
        z.ambientTemp = 24 + Math.floor(Math.random() * 30);
      }

      if (z.status === 'unsafe' && Math.random() < 0.5) {
        alert = { level: 'warn', text: `Zone ${z.id} reclassified to unsafe`, cam: findCam(prev, z.id, activeCam), time: nowTime() };
      }

      zones[idx] = z;
      setIncident({ ...prev, zones });
      if (alert) {
        alertSeq += 1;
        const withId = { ...alert, id: alertSeq };
        setAlerts((a) => [withId, ...a].slice(0, 10));
      }
    }

    tick();
    const timer = setInterval(tick, 2600);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  const value = useMemo<IncidentContextValue>(
    () => ({ incident, stage, alerts, activeCam, setActiveCam, createIncident, goLive }),
    [incident, stage, alerts, activeCam],
  );

  return <IncidentContext.Provider value={value}>{children}</IncidentContext.Provider>;
}

export function useIncident() {
  const ctx = useContext(IncidentContext);
  if (!ctx) throw new Error('useIncident must be used within IncidentProvider');
  return ctx;
}
