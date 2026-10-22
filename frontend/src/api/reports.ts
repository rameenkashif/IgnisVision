import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, authFetch, unwrap } from './client';
import { toApiError } from './errors';
import type { components } from './schema';

export type ReportOut = components['schemas']['ReportOut'];
type Status = 'draft' | 'dispatched' | 'active' | 'closed';

export function useIncidentSearch(f: {
  status?: Status[];
  q?: string;
  from?: string;
  to?: string;
}) {
  return useQuery({
    queryKey: ['incidents', 'search', f],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/incidents', {
          params: {
            query: {
              status: f.status?.length ? f.status : undefined,
              q: f.q || undefined,
              from: f.from ? new Date(`${f.from}T00:00:00`).toISOString() : undefined,
              to: f.to ? new Date(`${f.to}T23:59:59`).toISOString() : undefined,
              limit: 200,
            },
          },
        }),
      ),
  });
}

export function useReport(incidentId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['report', incidentId],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/incidents/{incident_id}/report', {
          params: { path: { incident_id: incidentId! } },
        }),
      ),
    enabled: !!incidentId && enabled,
    retry: false,
  });
}

export function useRegenerateReport(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/incidents/{incident_id}/report/regenerate', {
          params: { path: { incident_id: incidentId } },
        }),
      ),
    onSuccess: (r) => qc.setQueryData(['report', incidentId], r),
  });
}

export function useDeleteIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (incidentId: string) =>
      unwrap(
        api.DELETE('/api/v1/incidents/{incident_id}', {
          params: { path: { incident_id: incidentId } },
          body: { confirm: true },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['incidents'] }),
  });
}

/** Authenticated download (bearer token), saved via a temporary object URL. */
export async function downloadReportPdf(incidentId: string, code: string, lang: 'en' | 'ur') {
  const res = await authFetch(
    new Request(`/api/v1/incidents/${incidentId}/report.pdf?lang=${lang}`),
  );
  if (!res.ok) throw await toApiError(res);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), {
    href: url,
    download: `${code}-report-${lang}.pdf`,
  });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
