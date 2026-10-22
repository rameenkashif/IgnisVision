import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from './client';

export function useCaptureTargets() {
  return useQuery({
    queryKey: ['capture-targets'],
    queryFn: () => unwrap(api.GET('/api/v1/capture/targets')),
    refetchInterval: 15_000,
  });
}
