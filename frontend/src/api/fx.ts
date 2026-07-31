import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { FX } from '@/types/fx'

// React Query hook for the read-only `/api/v1/fx/` endpoint.
// Production FX acquisition is owned by the scheduled `refresh_fx`
// management command, not by browser-triggered mutations.

export function useFX() {
  return useQuery<FX[]>({
    queryKey: queryKeys.fx.all,
    queryFn: () => apiFetch<FX[]>('/fx/'),
  })
}
