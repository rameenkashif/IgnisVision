import { Navigate, Route, Routes } from 'react-router-dom';
import { Splash } from './pages/Splash';
import { Login } from './pages/Login';
import { LanguageSelect } from './pages/LanguageSelect';
import { AppShell } from './layouts/AppShell';
import { IncidentProvider } from './state/IncidentContext';
import { LiveMonitoring } from './pages/dashboard/LiveMonitoring';
import { CameraDemo } from './pages/dashboard/CameraDemo';
import { IncidentReports } from './pages/dashboard/IncidentReports';
import { ImageAnalysis } from './pages/dashboard/ImageAnalysis';
import { TeamDeployment } from './pages/dashboard/TeamDeployment';
import { TrainingSimulator } from './pages/dashboard/TrainingSimulator';
import { Settings } from './pages/dashboard/Settings';

function DashboardShell() {
  return (
    <IncidentProvider>
      <AppShell />
    </IncidentProvider>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Splash />} />
      <Route path="/login" element={<Login />} />
      <Route path="/language" element={<LanguageSelect />} />
      <Route path="/dashboard" element={<DashboardShell />}>
        <Route index element={<Navigate to="live" replace />} />
        <Route path="live" element={<LiveMonitoring />} />
        <Route path="demo" element={<CameraDemo />} />
        <Route path="reports" element={<IncidentReports />} />
        <Route path="annotate" element={<ImageAnalysis />} />
        <Route path="team" element={<TeamDeployment />} />
        <Route path="sim" element={<TrainingSimulator />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
