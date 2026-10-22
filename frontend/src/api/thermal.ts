import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, refreshSession, unwrap } from './client';
import { ApiError } from './errors';
import type { components } from './schema';
import { useAuth } from '../stores/auth';

type S = components['schemas'];
export type VictimOut = S['VictimOut'];
export type DetectionOut = S['DetectionOut'];
export type JobOut = S['JobOut'];
export type ThermalUpload = S['ThermalUploadOut'];
export type SampleFrame = S['SampleFrame'];

export const thermalKeys = {
  victims: (id: string) => ['victims', id] as const,
  uploads: (id: string) => ['thermal-uploads', id] as const,
  job: (id: string) => ['job', id] as const,
  detections: (mediaId: string) => ['detections', mediaId] as const,
  frames: (mediaId: string) => ['frames', mediaId] as const,
};

export function useVictims(incidentId: string | undefined) {
  return useQuery({
    queryKey: thermalKeys.victims(incidentId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/incidents/{incident_id}/victims', {
          params: { path: { incident_id: incidentId! } },
        }),
      ),
    enabled: !!incidentId,
  });
}

export function useThermalUploads(incidentId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: thermalKeys.uploads(incidentId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/incidents/{incident_id}/thermal-uploads', {
          params: { path: { incident_id: incidentId! } },
        }),
      ),
    enabled: !!incidentId && enabled,
  });
}

/** Polls until the job finishes (works for responders, who don't get the dashboard channel). */
export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: thermalKeys.job(jobId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/v1/jobs/{job_id}', { params: { path: { job_id: jobId! } } })),
    enabled: !!jobId,
    refetchInterval: (q) =>
      q.state.data && ['done', 'failed'].includes(q.state.data.status) ? false : 700,
  });
}

export function useDetections(mediaId: string | undefined, ready = true) {
  return useQuery({
    queryKey: thermalKeys.detections(mediaId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/media/{media_id}/detections', {
          params: { path: { media_id: mediaId! } },
        }),
      ),
    enabled: !!mediaId && ready,
  });
}

export function useUpdateVictim(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: VictimOut['status'] }) =>
      unwrap(
        api.PATCH('/api/v1/victims/{victim_id}', {
          params: { path: { victim_id: id } },
          body: { status },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: thermalKeys.victims(incidentId) }),
  });
}

/** Multipart upload with progress (fetch has no upload progress). Retries once after refresh. */
export function uploadThermal(
  incidentId: string,
  file: File,
  zoneId: string | null,
  onProgress: (fraction: number) => void,
): Promise<{ media_id: string; job_id: string }> {
  const send = (): Promise<{ status: number; body: unknown }> =>
    new Promise((resolve, reject) => {
      const form = new FormData();
      form.append('file', file);
      if (zoneId) form.append('zone_id', zoneId);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `/api/v1/incidents/${incidentId}/thermal-uploads`);
      xhr.withCredentials = true;
      const token = useAuth.getState().accessToken;
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onload = () => {
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          /* empty */
        }
        resolve({ status: xhr.status, body });
      };
      xhr.onerror = () => reject(new ApiError(0, 'network'));
      xhr.send(form);
    });

  return (async () => {
    let res = await send();
    if (res.status === 401 && (await refreshSession())) res = await send();
    if (res.status >= 200 && res.status < 300)
      return res.body as { media_id: string; job_id: string };
    const err = (res.body as { error?: { code: string; params: Record<string, unknown> } })?.error;
    throw new ApiError(res.status, err?.code ?? 'unknown', err?.params ?? {});
  })();
}

export function useFrames(mediaId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: thermalKeys.frames(mediaId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/media/{media_id}/frames', { params: { path: { media_id: mediaId! } } }),
      ),
    enabled: !!mediaId && enabled,
  });
}
