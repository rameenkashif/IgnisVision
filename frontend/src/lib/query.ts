import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/errors';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, err) =>
        count < 2 && !(err instanceof ApiError && [401, 403, 404, 410].includes(err.status)),
    },
  },
});
