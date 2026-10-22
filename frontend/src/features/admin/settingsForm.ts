import type { SystemSettings } from '../../api/admin';

export type Key = keyof SystemSettings;
/** A number field: [setting key, sub-key or null, min, max, step]. */
export type NumField = [Key, string | null, number, number, number];
export type Section = { id: string; keys: Key[]; fields: NumField[]; toggles?: [Key, string][] };

const U = (k: Key, sub: string): NumField => [k, sub, 0, 1, 0.01];
export const SECTIONS: Section[] = [
  {
    id: 'rpi',
    keys: [
      'rpi.weights',
      'rpi.posture_scores',
      'rpi.bands',
      'rpi.low_confidence_threshold',
      'rpi.low_confidence_factor',
    ],
    fields: [
      U('rpi.weights', 'w_p'),
      U('rpi.weights', 'w_c'),
      U('rpi.weights', 'w_r'),
      U('rpi.posture_scores', 'lying'),
      U('rpi.posture_scores', 'bending'),
      U('rpi.posture_scores', 'sitting'),
      U('rpi.posture_scores', 'standing'),
      U('rpi.bands', 'critical'),
      U('rpi.bands', 'high'),
      U('rpi.bands', 'medium'),
      ['rpi.low_confidence_threshold', null, 0, 1, 0.01],
      ['rpi.low_confidence_factor', null, 0, 1, 0.01],
    ],
  },
  {
    id: 'fusion',
    keys: ['zone_fusion'],
    fields: [
      'min_structure_share',
      'min_confidence',
      'caution_damage_conf',
      'unsafe_crack_spalling_share',
      'unsafe_collapse_conf',
      'blocked_floor_door_share',
      'blocked_frame_share',
    ].map((s) => U('zone_fusion', s)),
  },
  {
    id: 'timing',
    keys: [
      'stale_zone_seconds',
      'rapid_change_window_s',
      'analysis_failed_alert_interval_s',
      'capture_fps',
      'evacuation_threshold_pct',
    ],
    fields: [
      ['stale_zone_seconds', null, 10, 3600, 1],
      ['rapid_change_window_s', null, 5, 3600, 1],
      ['analysis_failed_alert_interval_s', null, 10, 3600, 1],
      ['capture_fps', null, 0.2, 5, 0.1],
      ['evacuation_threshold_pct', null, 0, 100, 1],
    ],
  },
  { id: 'data', keys: ['retention_days'], fields: [['retention_days', null, 1, 3650, 1]] },
  {
    id: 'ai',
    keys: ['llm.features'],
    fields: [],
    toggles: [
      ['llm.features', 'report_narrative'],
      ['llm.features', 'trainer_feedback'],
      ['llm.features', 'help_assistant'],
    ],
  },
  {
    id: 'trainer',
    keys: ['trainer.grading'],
    fields: [U('trainer.grading', 'adjacent_credit')],
    toggles: [['trainer.grading', 'partial_credit_adjacent']],
  },
];

export const path = (k: Key, sub: string | null) => (sub ? `${k}.${sub}` : k);
export const get = (s: SystemSettings, k: Key, sub: string | null): unknown =>
  sub ? (s[k] as Record<string, unknown> | null)?.[sub] : s[k];
export function set(s: SystemSettings, k: Key, sub: string | null, v: unknown): SystemSettings {
  return { ...s, [k]: sub ? { ...(s[k] as object), [sub]: v } : v };
}

/** Field-level checks mirroring backend services/settings.py; returns path → i18n key. */
export function validate(s: SystemSettings, section: Section): Record<string, string> {
  const errs: Record<string, string> = {};
  for (const [k, sub, min, max] of section.fields) {
    const v = get(s, k, sub);
    if (k === 'retention_days' && v === null) continue;
    if (typeof v !== 'number' || Number.isNaN(v)) errs[path(k, sub)] = 'admin.set.err.number';
    else if (v < min || v > max) errs[path(k, sub)] = 'admin.set.err.range';
  }
  if (section.id === 'rpi') {
    const b = s['rpi.bands'];
    if (!(b.critical > b.high && b.high > b.medium))
      errs['rpi.bands.critical'] = 'admin.set.err.bands';
    const w = s['rpi.weights'];
    if (w.w_p + w.w_c + w.w_r <= 0) errs['rpi.weights.w_p'] = 'admin.set.err.weights';
  }
  return errs;
}
