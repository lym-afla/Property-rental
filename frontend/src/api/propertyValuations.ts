import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { PropertyValuation } from '@/types/propertyValuation'

// React Query hooks for the `/api/v1/property-valuations/` ViewSet (Task 17).
//
// Pages typically want "all valuations for property X", so the list hook is
// keyed by property via the `byProperty` factory. Mutations invalidate the
// root key so every `byProperty` cache refetches.

export function usePropertyValuations(propertyId: number) {
  return useQuery<PropertyValuation[]>({
    queryKey: queryKeys.propertyValuations.byProperty(propertyId),
    queryFn: () =>
      apiFetch<PropertyValuation[]>('/property-valuations/', {
        query: { property: propertyId },
      }),
  })
}

export function usePropertyValuation(id: number) {
  return useQuery<PropertyValuation>({
    queryKey: queryKeys.propertyValuations.detail(id),
    queryFn: () => apiFetch<PropertyValuation>(`/property-valuations/${id}/`),
  })
}

export function useCreatePropertyValuation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<PropertyValuation>) =>
      apiFetch<PropertyValuation>('/property-valuations/', {
        method: 'POST',
        body: data,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.propertyValuations.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useUpdatePropertyValuation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number
      data: Partial<PropertyValuation>
    }) =>
      apiFetch<PropertyValuation>(`/property-valuations/${id}/`, {
        method: 'PATCH',
        body: data,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.propertyValuations.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useDeletePropertyValuation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/property-valuations/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.propertyValuations.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}
