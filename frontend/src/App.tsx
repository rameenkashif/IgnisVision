import { QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { RouterProvider } from 'react-router-dom';
import { queryClient } from './lib/query';
import { bootstrapSession } from './lib/session';
import { router } from './routes';
import { useAuth } from './stores/auth';

export default function App() {
  const { t } = useTranslation();
  const status = useAuth((s) => s.status);

  useEffect(() => {
    void bootstrapSession();
  }, []);

  if (status === 'unknown') {
    return (
      <div className="loader" role="status">
        {t('common.loading')}
      </div>
    );
  }
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
