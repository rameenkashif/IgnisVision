import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { keys, upsertAlert } from '../api/incidents';
import { thermalKeys } from '../api/thermal';
import type { AlertOut, IncidentDetail } from '../api/types';
import { useUi } from '../stores/ui';
import { LiveSocket, type SocketState } from './socket';

/** Live incident channel → TanStack Query cache. Returns the time of the last update. */
export function useIncidentStream(incidentId: string | undefined): Date | null {
  const qc = useQueryClient();
  const setLink = useUi((s) => s.setLink);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    if (!incidentId) return;
    const sock = new LiveSocket(`/ws/incidents/${incidentId}`, {
      onState: (s: SocketState) => setLink(s === 'closed' ? 'none' : s),
      onMessage: (msg) => {
        switch (msg.type) {
          case 'ready':
            // (Re)connected: refetch everything so nothing missed while offline is lost.
            void qc.invalidateQueries({ queryKey: keys.incident(incidentId) });
            void qc.invalidateQueries({ queryKey: keys.alerts(incidentId) });
            void qc.invalidateQueries({ queryKey: thermalKeys.victims(incidentId) });
            break;
          case 'incident.updated':
            qc.setQueryData(keys.incident(incidentId), msg.incident as IncidentDetail);
            break;
          case 'alert.created':
          case 'alert.acknowledged':
            upsertAlert(qc, incidentId, msg.alert as AlertOut);
            break;
          case 'assignment.changed':
            void qc.invalidateQueries({ queryKey: keys.assignments(incidentId) });
            break;
          case 'zone.updated':
            break; // the incident.updated that follows carries the new aggregate
          case 'victim.upserted':
            void qc.invalidateQueries({ queryKey: thermalKeys.victims(incidentId) });
            break;
          case 'job.progress':
            void qc.invalidateQueries({ queryKey: thermalKeys.uploads(incidentId) });
            void qc.invalidateQueries({ queryKey: thermalKeys.job(String(msg.job_id)) });
            break;
          case 'incident.deleted':
            void qc.invalidateQueries({ queryKey: ['incidents'] });
            break;
          default:
            return;
        }
        setLastUpdate(new Date());
      },
    });
    sock.start();
    return () => sock.stop();
  }, [incidentId, qc, setLink]);

  return lastUpdate;
}

/** Station channel: keeps incident lists fresh (new incident, status change, deletion). */
export function useStationStream(enabled: boolean): void {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    const sock = new LiveSocket('/ws/station', {
      onState: () => undefined,
      onMessage: (msg) => {
        if (msg.type.startsWith('incident.') || msg.type === 'ready') {
          void qc.invalidateQueries({ queryKey: ['incidents'] });
        }
      },
    });
    sock.start();
    return () => sock.stop();
  }, [enabled, qc]);
}
