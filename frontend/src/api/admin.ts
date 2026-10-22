import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from './client';
import type { components } from './schema';

type S = components['schemas'];
export type UserOut = S['UserOut'];
export type UserCreate = S['UserCreate'];
export type UserUpdate = S['UserUpdate'];
export type AuditOut = S['AuditOut'];
export type Role = UserOut['role'];
export const ROLES: Role[] = [
  'admin',
  'incident_commander',
  'field_responder',
  'training_staff',
  'trainee',
];

/** Admin-editable system settings (backend services/settings.py SCHEMAS). */
export type SystemSettings = {
  'rpi.weights': { w_p: number; w_c: number; w_r: number };
  'rpi.posture_scores': { lying: number; bending: number; sitting: number; standing: number };
  'rpi.low_confidence_factor': number;
  'rpi.low_confidence_threshold': number;
  'rpi.bands': { critical: number; high: number; medium: number };
  zone_fusion: {
    min_structure_share: number;
    min_confidence: number;
    blocked_floor_door_share: number;
    blocked_frame_share: number;
    unsafe_collapse_conf: number;
    unsafe_crack_spalling_share: number;
    caution_damage_conf: number;
  };
  stale_zone_seconds: number;
  rapid_change_window_s: number;
  analysis_failed_alert_interval_s: number;
  evacuation_threshold_pct: number;
  capture_fps: number;
  retention_days: number | null;
  'llm.features': { report_narrative: boolean; trainer_feedback: boolean; help_assistant: boolean };
  'trainer.grading': { partial_credit_adjacent: boolean; adjacent_credit: number };
};

export type SystemStatus = {
  status: 'ok' | 'warn';
  warnings: string[];
  checked_at: string;
  app: { version: string; environment: string; uptime_s: number };
  database: {
    ok: boolean;
    latency_ms: number;
    size_bytes: number;
    server_version: string;
    migration: string;
  };
  ml: {
    backend: string;
    device: string;
    models: Record<string, string>;
    fallback_reason: string | null;
    mock_scenario: string | null;
  };
  jobs: {
    by_status: Record<string, number>;
    failed_24h: number;
    queue_depth: number;
    workers: number;
  };
  storage: {
    media_files: number;
    media_bytes: number;
    disk_total: number | null;
    disk_free: number | null;
  };
  backups:
    | { available: false }
    | {
        available: true;
        count: number;
        last_at: string | null;
        latest_file: string | null;
        latest_bytes: number | null;
        stale: boolean;
      };
  llm: {
    provider: string;
    active: boolean;
    model: string | null;
    features: Record<string, boolean>;
  };
  users: { active_by_role: Record<string, number>; active_sessions: number };
  live: { open_incidents: number; live_connections: number };
};

export const adminKeys = {
  users: (f: object) => ['admin', 'users', f] as const,
  settings: ['admin', 'settings'] as const,
  status: ['admin', 'status'] as const,
  audit: (f: object) => ['admin', 'audit', f] as const,
  facets: ['admin', 'audit-facets'] as const,
};

export function useUsers(f: { role?: Role; is_active?: boolean; q?: string; offset: number }) {
  return useQuery({
    queryKey: adminKeys.users(f),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/users', {
          params: {
            query: {
              role: f.role,
              is_active: f.is_active,
              q: f.q || undefined,
              limit: 50,
              offset: f.offset,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

function useInvalidateUsers() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: ['admin', 'users'] });
}

export function useCreateUser() {
  const done = useInvalidateUsers();
  return useMutation({
    mutationFn: (body: UserCreate) => unwrap(api.POST('/api/v1/users', { body })),
    onSuccess: done,
  });
}

export function useUpdateUser() {
  const done = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UserUpdate }) =>
      unwrap(api.PATCH('/api/v1/users/{user_id}', { params: { path: { user_id: id } }, body })),
    onSuccess: done,
  });
}

export function useDeactivateUser() {
  const done = useInvalidateUsers();
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.POST('/api/v1/users/{user_id}/deactivate', {
          params: { path: { user_id: id } },
          body: { confirm: true },
        }),
      ),
    onSuccess: done,
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.POST('/api/v1/users/{user_id}/reset-password', {
          params: { path: { user_id: id } },
          body: { confirm: true },
        }),
      ),
  });
}

export function useAdminSettings() {
  return useQuery({
    queryKey: adminKeys.settings,
    queryFn: async () =>
      (await unwrap(api.GET('/api/v1/admin/settings'))) as unknown as SystemSettings,
  });
}

export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (changes: Partial<SystemSettings>) =>
      (await unwrap(
        api.PATCH('/api/v1/admin/settings', { body: changes as unknown as Record<string, never> }),
      )) as unknown as SystemSettings,
    onSuccess: (s) => {
      qc.setQueryData(adminKeys.settings, s);
      void qc.invalidateQueries({ queryKey: ['settings'] });
    },
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: adminKeys.status,
    queryFn: async () => (await unwrap(api.GET('/api/v1/admin/status'))) as unknown as SystemStatus,
    refetchInterval: 15_000,
  });
}

export function useAudit(f: {
  action?: string;
  entity_type?: string;
  from?: string;
  to?: string;
  offset: number;
}) {
  return useQuery({
    queryKey: adminKeys.audit(f),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/admin/audit-logs', {
          params: {
            query: {
              action: f.action || undefined,
              entity_type: f.entity_type || undefined,
              from: f.from ? new Date(`${f.from}T00:00:00`).toISOString() : undefined,
              to: f.to ? new Date(`${f.to}T23:59:59`).toISOString() : undefined,
              limit: 50,
              offset: f.offset,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useAuditFacets() {
  return useQuery({
    queryKey: adminKeys.facets,
    queryFn: () => unwrap(api.GET('/api/v1/admin/audit-logs/facets')),
  });
}

export function useAskHelp() {
  return useMutation({
    mutationFn: (body: { question: string; topic: string; context: string; lang: 'en' | 'ur' }) =>
      unwrap(api.POST('/api/v1/help/ask', { body })),
  });
}

/** Settings every signed-in user may read (dashboard thresholds, enabled AI features). */
export function usePublicSettings() {
  return useQuery({
    queryKey: ['settings', 'public'],
    queryFn: async () =>
      (await unwrap(api.GET('/api/v1/settings'))) as unknown as Pick<
        SystemSettings,
        | 'rpi.bands'
        | 'stale_zone_seconds'
        | 'evacuation_threshold_pct'
        | 'capture_fps'
        | 'llm.features'
      >,
    staleTime: 60_000,
  });
}
