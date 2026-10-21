import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../stores/auth';
import { api, refreshSession, unwrap } from './client';
import { ApiError } from './errors';
import type { components } from './schema';

type S = components['schemas'];
export type ScenarioSummary = S['ScenarioSummary'];
export type ScenarioDetail = S['ScenarioDetail'];
export type AttemptOut = S['AttemptOut'];
export type AttemptSummary = S['AttemptSummary'];
export type ItemResult = S['ItemResult'];
export type TargetResult = S['TargetResult'];
export type AdminScenario = S['AdminScenario'];
export type AdminScenarioDetail = S['AdminScenarioDetail'];
export type AdminItem = S['AdminItem'];
export type ScenarioIn = S['ScenarioIn'];
export type ZoneLabel = 'safe' | 'caution' | 'unsafe' | 'blocked';
export type PostureLabel = 'standing' | 'sitting' | 'lying' | 'bending';
export const ZONE_LABELS: ZoneLabel[] = ['safe', 'caution', 'unsafe', 'blocked'];
export const POSTURE_LABELS: PostureLabel[] = ['standing', 'sitting', 'lying', 'bending'];

export type Point = [number, number];
export type Box = [number, number, number, number];
export type GroundTruth = {
  type: 'zone' | 'posture';
  regions: { id: string; polygon: Point[]; status: ZoneLabel }[];
  people: { id: string; bbox: Box; posture: PostureLabel }[];
  explanation_en: string;
  explanation_ur: string;
  frame_s: number | null;
};
export type Answers = Record<
  string,
  { regions: Record<string, ZoneLabel>; people: Record<string, PostureLabel> }
>;

/** A stage item (trainee, result and admin views share this shape). */
export type StageItem = {
  media_kind: 'image' | 'video';
  media_url?: string | null;
  frame_s?: number | null;
  regions: { id: string; polygon: Point[] }[];
  people: { id: string; bbox: Box }[];
};

export const trainingKeys = {
  scenarios: ['training', 'scenarios'] as const,
  scenario: (id: string) => ['training', 'scenario', id] as const,
  attempt: (id: string) => ['training', 'attempt', id] as const,
  attempts: (f: object) => ['training', 'attempts', f] as const,
  admin: ['training', 'admin'] as const,
  adminScenario: (id: string) => ['training', 'admin', id] as const,
};

export function useScenarios() {
  return useQuery({
    queryKey: trainingKeys.scenarios,
    queryFn: () => unwrap(api.GET('/api/v1/training/scenarios')),
  });
}

export function useScenario(id: string | undefined) {
  return useQuery({
    queryKey: trainingKeys.scenario(id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/training/scenarios/{scenario_id}', {
          params: { path: { scenario_id: id! } },
        }),
      ),
    enabled: !!id,
  });
}

export function useStartAttempt() {
  return useMutation({
    mutationFn: (scenarioId: string) =>
      unwrap(
        api.POST('/api/v1/training/scenarios/{scenario_id}/attempts', {
          params: { path: { scenario_id: scenarioId } },
        }),
      ),
  });
}

export function useSubmitAttempt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, answers }: { id: string; answers: Answers }) =>
      unwrap(
        api.POST('/api/v1/training/attempts/{attempt_id}/submit', {
          params: { path: { attempt_id: id } },
          body: { answers },
        }),
      ),
    onSuccess: (a) => {
      qc.setQueryData(trainingKeys.attempt(a.id), a);
      void qc.invalidateQueries({ queryKey: ['training', 'scenarios'] });
      void qc.invalidateQueries({ queryKey: ['training', 'attempts'] });
    },
  });
}

/** Polls while the optional LLM feedback is still being written. */
export function useAttempt(id: string | undefined) {
  return useQuery({
    queryKey: trainingKeys.attempt(id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/training/attempts/{attempt_id}', {
          params: { path: { attempt_id: id! } },
        }),
      ),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.llm_feedback_pending ? 2000 : false),
  });
}

export function useAttempts(f: { user_id?: string; scenario_id?: string }) {
  return useQuery({
    queryKey: trainingKeys.attempts(f),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/training/attempts', {
          params: {
            query: { user_id: f.user_id || undefined, scenario_id: f.scenario_id || undefined },
          },
        }),
      ),
  });
}

// ---- admin ----

export function useAdminScenarios() {
  return useQuery({
    queryKey: trainingKeys.admin,
    queryFn: () => unwrap(api.GET('/api/v1/admin/scenarios')),
  });
}

export function useAdminScenario(id: string | undefined) {
  return useQuery({
    queryKey: trainingKeys.adminScenario(id ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/admin/scenarios/{scenario_id}', {
          params: { path: { scenario_id: id! } },
        }),
      ),
    enabled: !!id,
  });
}

function useAdminInvalidate(id?: string) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: trainingKeys.admin });
    if (id) void qc.invalidateQueries({ queryKey: trainingKeys.adminScenario(id) });
    void qc.invalidateQueries({ queryKey: trainingKeys.scenarios });
  };
}

export function useCreateScenario() {
  const done = useAdminInvalidate();
  return useMutation({
    mutationFn: (body: ScenarioIn) => unwrap(api.POST('/api/v1/admin/scenarios', { body })),
    onSuccess: done,
  });
}

export function useUpdateScenario(id: string) {
  const done = useAdminInvalidate(id);
  return useMutation({
    mutationFn: (body: Partial<ScenarioIn>) =>
      unwrap(
        api.PATCH('/api/v1/admin/scenarios/{scenario_id}', {
          params: { path: { scenario_id: id } },
          body,
        }),
      ),
    onSuccess: done,
  });
}

export function useDeleteScenario() {
  const done = useAdminInvalidate();
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.DELETE('/api/v1/admin/scenarios/{scenario_id}', {
          params: { path: { scenario_id: id } },
          body: { confirm: true },
        }),
      ),
    onSuccess: done,
  });
}

export function useSaveItem(scenarioId: string) {
  const done = useAdminInvalidate(scenarioId);
  return useMutation({
    mutationFn: ({ itemId, ground_truth }: { itemId: string; ground_truth: GroundTruth }) =>
      unwrap(
        api.PATCH('/api/v1/admin/scenarios/{scenario_id}/items/{item_id}', {
          params: { path: { scenario_id: scenarioId, item_id: itemId } },
          body: { ground_truth },
        }),
      ),
    onSuccess: done,
  });
}

export function useDeleteItem(scenarioId: string) {
  const done = useAdminInvalidate(scenarioId);
  return useMutation({
    mutationFn: (itemId: string) =>
      unwrap(
        api.DELETE('/api/v1/admin/scenarios/{scenario_id}/items/{item_id}', {
          params: { path: { scenario_id: scenarioId, item_id: itemId } },
        }),
      ),
    onSuccess: done,
  });
}

export function useRecompute(scenarioId: string) {
  const done = useAdminInvalidate(scenarioId);
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/admin/scenarios/{scenario_id}/recompute-reference', {
          params: { path: { scenario_id: scenarioId } },
        }),
      ),
    onSuccess: done,
  });
}

/** Multipart upload with progress; retries once after a token refresh. */
export function uploadScenarioItem(
  scenarioId: string,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<AdminItem> {
  const send = (): Promise<{ status: number; body: unknown }> =>
    new Promise((resolve, reject) => {
      const form = new FormData();
      form.append('file', file);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `/api/v1/admin/scenarios/${scenarioId}/items`);
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
    if (res.status >= 200 && res.status < 300) return res.body as AdminItem;
    const err = (res.body as { error?: { code: string; params: Record<string, unknown> } })?.error;
    throw new ApiError(res.status, err?.code ?? 'unknown', err?.params ?? {});
  })();
}
