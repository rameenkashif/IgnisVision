import { homeFor, navFor, type Role } from './nav';

const keys = (r: Role) => navFor(r).map((i) => i.key);

describe('navigation by role (HANDOFF §6)', () => {
  it('commander sees operations and training', () => {
    expect(keys('incident_commander')).toEqual([
      'live',
      'capture',
      'analysis',
      'reports',
      'team',
      'trainer',
      'trainerResults',
      'settings',
      'help',
    ]);
  });

  it('responder gets capture/analysis/team/trainer, no live dashboard or reports', () => {
    expect(keys('field_responder')).toEqual([
      'capture',
      'analysis',
      'team',
      'trainer',
      'settings',
      'help',
    ]);
  });

  it('trainee sees no incident screens', () => {
    expect(keys('trainee')).toEqual(['trainer', 'settings', 'help']);
  });

  it("training staff can see everyone's results", () => {
    expect(keys('training_staff')).toEqual(['trainer', 'trainerResults', 'settings', 'help']);
  });

  it('admin gets administration, read-only ops views, no trainer attempts', () => {
    expect(keys('admin')).toEqual([
      'live',
      'reports',
      'team',
      'trainerResults',
      'admin',
      'settings',
      'help',
    ]);
  });

  it('every role has Settings and Help', () => {
    (
      ['admin', 'incident_commander', 'field_responder', 'trainee', 'training_staff'] as Role[]
    ).forEach((r) => expect(keys(r)).toEqual(expect.arrayContaining(['settings', 'help'])));
  });

  it('lands each role on a screen it can open', () => {
    expect(homeFor('incident_commander')).toBe('/live');
    expect(homeFor('field_responder')).toBe('/capture');
    expect(homeFor('trainee')).toBe('/trainer');
    (
      ['admin', 'incident_commander', 'field_responder', 'trainee', 'training_staff'] as Role[]
    ).forEach((r) => expect(navFor(r).map((i) => i.path)).toContain(homeFor(r)));
  });
});
