import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { FX, FXBrowseParams, FXDetails, SharedFXPage } from '@/types/fx'

export function useFX(params: FXBrowseParams = {}, continuation: string | null = null, session = '') {
  return useQuery<FX[] | SharedFXPage>({
    queryKey: queryKeys.fx.browse(params, continuation, session),
    queryFn: () => continuation
      ? apiFetch<SharedFXPage>(continuation.replace(/^\/api\/v1/, ''))
      : apiFetch<FX[] | SharedFXPage>('/fx/', { query: params }),
    refetchOnWindowFocus: (query) => Array.isArray(query.state.data),
    refetchOnReconnect: (query) => Array.isArray(query.state.data),
  })
}

export function useFXDetails(token: string | null) {
  return useQuery<FXDetails>({
    queryKey: [...queryKeys.fx.all, 'details', token],
    queryFn: () => apiFetch<FXDetails>('/fx/details/', { query: { token: token ?? undefined } }),
    enabled: Boolean(token),
    retry: false,
  })
}
