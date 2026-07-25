import { Navigate, Route, Routes } from 'react-router-dom';
import { Splash } from './pages/Splash';
import { Login } from './pages/Login';
import { LanguageSelect } from './pages/LanguageSelect';
import { Dashboard } from './pages/Dashboard';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Splash />} />
      <Route path="/login" element={<Login />} />
      <Route path="/language" element={<LanguageSelect />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
