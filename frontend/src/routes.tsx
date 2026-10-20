import type { ReactNode } from 'react';
import { createBrowserRouter, type RouteObject } from 'react-router-dom';
import { ComingSoon } from './components/ComingSoon';
import { HelpIndex, HelpTopic } from './features/help/Help';
import { ChangePassword } from './features/onboarding/ChangePassword';
import { Language } from './features/onboarding/Language';
import { Onboarding } from './features/onboarding/Onboarding';
import { SignIn } from './features/onboarding/SignIn';
import { Splash } from './features/onboarding/Splash';
import { SettingsPage } from './features/settings/SettingsPage';
import { AppShell, type RouteHandle } from './features/shell/AppShell';
import {
  NotFound,
  RedirectHome,
  RequireAuth,
  RequireNav,
  RequireSession,
} from './features/shell/guards';

function guarded(navKey: string, element: ReactNode, handle: RouteHandle = {}): RouteObject {
  return {
    element: <RequireNav navKey={navKey}>{element}</RequireNav>,
    handle: { help: navKey, ...handle },
  };
}

export const routes: RouteObject[] = [
  { path: '/', element: <Splash /> },
  { path: '/signin', element: <SignIn /> },
  {
    path: '/language',
    element: (
      <RequireSession>
        <Language />
      </RequireSession>
    ),
  },
  {
    path: '/onboarding',
    element: (
      <RequireSession>
        <Onboarding />
      </RequireSession>
    ),
  },
  {
    path: '/change-password',
    element: (
      <RequireSession>
        <ChangePassword />
      </RequireSession>
    ),
  },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { path: '/home', element: <RedirectHome /> },
      { path: '/live', ...guarded('live', <ComingSoon page="live" />) },
      { path: '/capture', ...guarded('capture', <ComingSoon page="capture" />, { camera: true }) },
      { path: '/analysis', ...guarded('analysis', <ComingSoon page="analysis" />) },
      { path: '/reports', ...guarded('reports', <ComingSoon page="reports" />) },
      { path: '/team', ...guarded('team', <ComingSoon page="team" />) },
      { path: '/trainer', ...guarded('trainer', <ComingSoon page="trainer" />) },
      {
        path: '/trainer/results',
        ...guarded('trainerResults', <ComingSoon page="trainerResults" />, { help: 'trainer' }),
      },
      { path: '/admin/*', ...guarded('admin', <ComingSoon page="admin" />) },
      { path: '/settings', ...guarded('settings', <SettingsPage />) },
      { path: '/help', element: <HelpIndex />, handle: { help: 'getting-started' } },
      { path: '/help/:topic', element: <HelpTopic />, handle: { help: 'getting-started' } },
      { path: '*', element: <NotFound /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
