import type { Role } from './nav';

/** Walkthrough tailored to the role (SRS §3.1.2). Replayable from Settings (?replay=1). */
export function stepsFor(role: Role): string[] {
  const middle: Record<Role, string[]> = {
    incident_commander: ['live', 'capture', 'analysis', 'reports'],
    field_responder: ['capture', 'analysis'],
    trainee: ['trainer'],
    training_staff: ['trainer'],
    admin: ['admin', 'reports'],
  };
  return ['welcome', 'disclaimer', ...middle[role], 'controls'];
}
