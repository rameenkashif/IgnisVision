import type { components } from '../api/schema';

export type Role = components['schemas']['UserOut']['role'];

export type NavItem = {
  key: string; // i18n: nav.<key>, pages.<key>, help.topics.<help>
  path: string;
  icon: string;
  group: 'operations' | 'training' | 'system';
  roles: readonly Role[];
};

const ALL: readonly Role[] = [
  'admin',
  'incident_commander',
  'field_responder',
  'trainee',
  'training_staff',
];

/** Navigation by role — mirrors the access matrix in HANDOFF §6 (enforced again server-side). */
export const NAV: readonly NavItem[] = [
  {
    key: 'live',
    path: '/live',
    icon: '◉',
    group: 'operations',
    roles: ['incident_commander', 'admin'],
  },
  {
    key: 'capture',
    path: '/capture',
    icon: '●',
    group: 'operations',
    roles: ['incident_commander', 'field_responder'],
  },
  {
    key: 'analysis',
    path: '/analysis',
    icon: '✎',
    group: 'operations',
    roles: ['incident_commander', 'field_responder'],
  },
  {
    key: 'reports',
    path: '/reports',
    icon: '☰',
    group: 'operations',
    roles: ['incident_commander', 'admin'],
  },
  {
    key: 'team',
    path: '/team',
    icon: '☉',
    group: 'operations',
    roles: ['incident_commander', 'admin', 'field_responder'],
  },
  {
    key: 'trainer',
    path: '/trainer',
    icon: '▶',
    group: 'training',
    roles: ['incident_commander', 'field_responder', 'trainee', 'training_staff'],
  },
  {
    key: 'trainerResults',
    path: '/trainer/results',
    icon: '▤',
    group: 'training',
    roles: ['admin', 'incident_commander', 'training_staff'],
  },
  { key: 'admin', path: '/admin', icon: '◈', group: 'system', roles: ['admin'] },
  { key: 'settings', path: '/settings', icon: '⚙', group: 'system', roles: ALL },
  { key: 'help', path: '/help', icon: '?', group: 'system', roles: ALL },
];

export const GROUPS = ['operations', 'training', 'system'] as const;

export function navFor(role: Role): NavItem[] {
  return NAV.filter((i) => i.roles.includes(role));
}

export function canAccess(role: Role, key: string): boolean {
  return NAV.find((i) => i.key === key)?.roles.includes(role) ?? false;
}

/** Landing screen after sign-in. */
export function homeFor(role: Role): string {
  switch (role) {
    case 'incident_commander':
    case 'admin':
      return '/live';
    case 'field_responder':
      return '/capture';
    default:
      return '/trainer';
  }
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join('');
}
