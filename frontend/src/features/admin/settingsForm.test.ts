import type { SystemSettings } from '../../api/admin';
import { SECTIONS, set, validate } from './settingsForm';

const base: SystemSettings = {
  'rpi.weights': { w_p: 0.6, w_c: 0.25, w_r: 0.15 },
  'rpi.posture_scores': { lying: 1, bending: 0.6, sitting: 0.5, standing: 0.2 },
  'rpi.low_confidence_factor': 0.9,
  'rpi.low_confidence_threshold': 0.6,
  'rpi.bands': { critical: 0.75, high: 0.55, medium: 0.35 },
  zone_fusion: {
    min_structure_share: 0.15,
    min_confidence: 0.35,
    blocked_floor_door_share: 0.25,
    blocked_frame_share: 0.35,
    unsafe_collapse_conf: 0.5,
    unsafe_crack_spalling_share: 0.05,
    caution_damage_conf: 0.4,
  },
  stale_zone_seconds: 120,
  rapid_change_window_s: 60,
  analysis_failed_alert_interval_s: 60,
  evacuation_threshold_pct: 40,
  capture_fps: 1,
  retention_days: null,
  'llm.features': { report_narrative: false, trainer_feedback: false, help_assistant: false },
  'trainer.grading': { partial_credit_adjacent: false, adjacent_credit: 0.5 },
};
const section = (id: string) => SECTIONS.find((s) => s.id === id)!;

test('defaults are valid in every section', () => {
  for (const s of SECTIONS) expect(validate(base, s), s.id).toEqual({});
});

test('mirrors the backend rules', () => {
  expect(validate(set(base, 'rpi.bands', 'high', 0.8), section('rpi'))).toEqual({
    'rpi.bands.critical': 'admin.set.err.bands',
  });
  expect(validate(set(base, 'zone_fusion', 'min_confidence', 1.5), section('fusion'))).toEqual({
    'zone_fusion.min_confidence': 'admin.set.err.range',
  });
  expect(validate(set(base, 'capture_fps', null, NaN), section('timing'))).toEqual({
    capture_fps: 'admin.set.err.number',
  });
  expect(validate(set(base, 'retention_days', null, 0), section('data'))).toEqual({
    retention_days: 'admin.set.err.range',
  });
});
