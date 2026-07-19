import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { FX } from '@/types/fx'

// React Query hooks for the `/api/v1/fx/` ViewSet (Task 17) + the
// `FXViewSet.update_rates` action.
//
// Updating FX rates changes how transactions convert across currencies, so
// `useUpdateFX` invalidates `fx.all` AND `chart-data` AND `transactions`
// (caches that depend on FX-derived amounts must be refetched).

export function useFX() {
  return useQuery<FX[]>({
    queryKey: queryKeys.fx.all,
    queryFn: () => apiFetch<FX[]>('/fx/'),
  })
}

export function useCreateFX() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<FX>) =>
      apiFetch<FX>('/fx/', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.fx.all })
    },
  })
}

export function useUpdateFXRate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<FX> }) =>
      apiFetch<FX>(`/fx/${id}/`, { method: 'PATCH', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.fx.all })
      qc.invalidateQueries({ queryKey: queryKeys.transactions.all })
      qc.invalidateQueries({ queryKey: queryKeys.chartData.all })
    },
  })
}

export function useDeleteFX() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/fx/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.fx.all })
    },
  })
}

// POST /fx/update/ -> 200 `{detail: "FX rates updated"}` (FXViewSet.update_rates).
// Refetches yfinance-derived rates for every property owned by the requester.
export function useUpdateFX() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<{ detail: string }>('/fx/update/', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.fx.all })
      qc.invalidateQueries({ queryKey: queryKeys.transactions.all })
      qc.invalidateQueries({ queryKey: queryKeys.chartData.all })
    },
  })
}
