import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from './client';
import type { AlertOut, IncidentCreate, IncidentDetail } from './types';

export const keys = {
  incidents: (status?: string[]) => ['incidents', status ?? 'all'] as const,
  incident: (id: string) => ['incident', id] as const,
  alerts: (id: string) => ['alerts', id] as const,
  assignments: (id: string) => ['assignments', id] as const,
  assessments: (zoneId: string) => ['assessments', zoneId] as const,
  responders: ['responders'] as const,
  mine: ['assignments', 'mine'] as const,
};

export const OPEN: ('dispatched' | 'active')[] = ['dispatched', 'active'];

export function useIncidents(status?: ('draft' | 'dispatched' | 'active' | 'closed')[]) {
  return useQuery({
    queryKey: keys.incidents(status),
    queryFn: () =>
      unwrap(api.GET('/api/v1/incidents', { params: { query: { status, limit: 50 } } })),
  });
}

export function useIncident(id: string | undefined) {
  return useQuery({
    queryKey: keys.incident(id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/incidents/{incident_id}', { params: { path: { incident_id: id! } } }),
      ),
    enabled: !!id,
  });
}

export function useAlerts(id: string | undefined) {
  return useQuery({
    queryKey: keys.alerts(id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/incidents/{incident_id}/alerts', {
          params: { path: { incident_id: id! }, query: { limit: 100 } },
        }),
      ),
    enabled: !!id,
  });
}

export function useAssignmentHistory(id: string | undefined) {
  return useQuery({
    queryKey: keys.assignments(id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/incidents/{incident_id}/assignments', {
          params: { path: { incident_id: id! }, query: { include_history: true } },
        }),
      ),
    enabled: !!id,
  });
}

export function useZoneHistory(zoneId: string | undefined) {
  return useQuery({
    queryKey: keys.assessments(zoneId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/zones/{zone_id}/assessments', {
          params: { path: { zone_id: zoneId! }, query: { limit: 20 } },
        }),
      ),
    enabled: !!zoneId,
  });
}

export function useResponders(enabled = true) {
  return useQuery({
    queryKey: keys.responders,
    queryFn: () => unwrap(api.GET('/api/v1/responders')),
    enabled,
  });
}

export function useMyAssignments(enabled = true) {
  return useQuery({
    queryKey: keys.mine,
    queryFn: () => unwrap(api.GET('/api/v1/assignments/mine')),
    enabled,
  });
}

/** Mutations update the incident cache from the response; the WebSocket keeps others in sync. */
function useIncidentMutation<V>(fn: (v: V) => Promise<IncidentDetail>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (inc) => {
      qc.setQueryData(keys.incident(inc.id), inc);
      void qc.invalidateQueries({ queryKey: ['incidents'] });
      void qc.invalidateQueries({ queryKey: keys.assignments(inc.id) });
      void qc.invalidateQueries({ queryKey: keys.responders });
    },
  });
}

export function useCreateIncident() {
  return useIncidentMutation((body: IncidentCreate) =>
    unwrap(api.POST('/api/v1/incidents', { body })),
  );
}

export function useActivateIncident() {
  return useIncidentMutation((id: string) =>
    unwrap(
      api.POST('/api/v1/incidents/{incident_id}/activate', {
        params: { path: { incident_id: id } },
      }),
    ),
  );
}

export function useCloseIncident() {
  return useIncidentMutation((id: string) =>
    unwrap(
      api.POST('/api/v1/incidents/{incident_id}/close', {
        params: { path: { incident_id: id } },
        body: { confirm: true },
      }),
    ),
  );
}

export function useAssign(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      user_id: string;
      zone_id?: string | null;
      device_label?: string | null;
    }) =>
      unwrap(
        api.POST('/api/v1/incidents/{incident_id}/assignments', {
          params: { path: { incident_id: incidentId } },
          body,
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.incident(incidentId) });
      void qc.invalidateQueries({ queryKey: keys.assignments(incidentId) });
      void qc.invalidateQueries({ queryKey: keys.responders });
    },
  });
}

export function useUnassign(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) =>
      unwrap(
        api.DELETE('/api/v1/assignments/{assignment_id}', {
          params: { path: { assignment_id: assignmentId } },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.incident(incidentId) });
      void qc.invalidateQueries({ queryKey: keys.assignments(incidentId) });
      void qc.invalidateQueries({ queryKey: keys.responders });
    },
  });
}

export function useRenameZone(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ zoneId, label }: { zoneId: string; label: string }) =>
      unwrap(
        api.PATCH('/api/v1/zones/{zone_id}', {
          params: { path: { zone_id: zoneId } },
          body: { label },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.incident(incidentId) }),
  });
}

export function useAckAlert(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) =>
      unwrap(
        api.POST('/api/v1/alerts/{alert_id}/ack', { params: { path: { alert_id: alertId } } }),
      ),
    onSuccess: (alert) => upsertAlert(qc, incidentId, alert),
  });
}

export function upsertAlert(
  qc: ReturnType<typeof useQueryClient>,
  incidentId: string,
  alert: AlertOut,
): void {
  qc.setQueryData<{ items: AlertOut[]; total: number }>(keys.alerts(incidentId), (old) => {
    if (!old) return old;
    const exists = old.items.some((a) => a.id === alert.id);
    return exists
      ? { ...old, items: old.items.map((a) => (a.id === alert.id ? alert : a)) }
      : { items: [alert, ...old.items], total: old.total + 1 };
  });
}
