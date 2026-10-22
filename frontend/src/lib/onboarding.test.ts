import { stepsFor } from './onboarding';

it('every role starts with the welcome + disclaimer and ends with controls', () => {
  for (const role of [
    'admin',
    'incident_commander',
    'field_responder',
    'trainee',
    'training_staff',
  ] as const) {
    const s = stepsFor(role);
    expect(s.slice(0, 2)).toEqual(['welcome', 'disclaimer']);
    expect(s.at(-1)).toBe('controls');
  }
  expect(stepsFor('field_responder')).toContain('capture');
  expect(stepsFor('trainee')).not.toContain('live');
});
