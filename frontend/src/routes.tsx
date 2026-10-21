import type { ReactNode } from 'react';
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
import { ComingSoon } from './components/ComingSoon';
import { AnalysisPage } from './features/analysis/AnalysisPage';
import { CapturePage } from './features/capture/CapturePage';
import { HelpIndex, HelpTopic } from './features/help/Help';
import { ChangePassword } from './features/onboarding/ChangePassword';
import { Language } from './features/onboarding/Language';
import { Onboarding } from './features/onboarding/Onboarding';
import { SignIn } from './features/onboarding/SignIn';
import { Splash } from './features/onboarding/Splash';
import { LivePage } from './features/live/LivePage';
import { SettingsPage } from './features/settings/SettingsPage';
import { TeamPage } from './features/team/TeamPage';
import { AttemptPage } from './features/trainer/AttemptPage';
import { AttemptResult } from './features/trainer/AttemptResult';
import { TrainerPage } from './features/trainer/TrainerPage';
import { TrainerResults } from './features/trainer/TrainerResults';
import { AdminScenarios } from './features/admin/AdminScenarios';
import { ScenarioEditor } from './features/admin/ScenarioEditor';
import { ReportDetail } from './features/reports/ReportDetail';
import { ReportsPage } from './features/reports/ReportsPage';
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
      { path: '/live', ...guarded('live', <LivePage />) },
      { path: '/capture', ...guarded('capture', <CapturePage />, { camera: true }) },
      { path: '/analysis', ...guarded('analysis', <AnalysisPage />) },
      { path: '/reports', ...guarded('reports', <ReportsPage />) },
      { path: '/reports/:incidentId', ...guarded('reports', <ReportDetail />) },
      { path: '/team', ...guarded('team', <TeamPage />) },
      { path: '/trainer', ...guarded('trainer', <TrainerPage />) },
      {
        path: '/trainer/results',
        ...guarded('trainerResults', <TrainerResults />, { help: 'trainer' }),
      },
      // Results: the owner (any trainer role) or staff/commanders/admins; the API decides.
      {
        path: '/trainer/attempts/:attemptId',
        element: <AttemptResult />,
        handle: { help: 'trainer' },
      },
      { path: '/trainer/:scenarioId', ...guarded('trainer', <AttemptPage />) },
      { path: '/admin', element: <Navigate to="/admin/scenarios" replace /> },
      { path: '/admin/scenarios', ...guarded('admin', <AdminScenarios />) },
      { path: '/admin/scenarios/:scenarioId', ...guarded('admin', <ScenarioEditor />) },
      { path: '/admin/*', ...guarded('admin', <ComingSoon page="admin" />) },
      { path: '/settings', ...guarded('settings', <SettingsPage />) },
      { path: '/help', element: <HelpIndex />, handle: { help: 'getting-started' } },
      { path: '/help/:topic', element: <HelpTopic />, handle: { help: 'getting-started' } },
      { path: '*', element: <NotFound /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
