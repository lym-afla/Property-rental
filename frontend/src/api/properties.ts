import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { Property, PropertyWithStats } from '@/types/property'

// React Query hooks for the `/api/v1/properties/` ViewSet (Task 17).
//
// Cascade invalidation: every property mutation touches BOTH `properties.all`
// AND `properties.withStats` — the with_stats endpoint joins on Transaction,
// so any change to a property's core shape or its transactions makes the
// aggregated stats stale.

export function useProperties() {
  return useQuery<Property[]>({
    queryKey: queryKeys.properties.all,
    queryFn: () => apiFetch<Property[]>('/properties/'),
  })
}

export function usePropertiesWithStats(asOf?: string, currency?: string) {
  return useQuery<PropertyWithStats[]>({
    queryKey: queryKeys.properties.withStats(asOf, currency),
    queryFn: () =>
      apiFetch<PropertyWithStats[]>('/properties/with_stats/', {
        query: { as_of: asOf, currency },
      }),
  })
}

export function useProperty(id: number) {
  return useQuery<Property>({
    queryKey: queryKeys.properties.detail(id),
    queryFn: () => apiFetch<Property>(`/properties/${id}/`),
  })
}

export function useCreateProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Property>) =>
      apiFetch<Property>('/properties/', { method: 'POST', body: data }),
    onSuccess: () => {
      // Invalidate the parent key (covers every properties.* variant,
      // including all with-stats (asOf, currency) tuples) AND the
      // with-stats base key explicitly so the cascade is obvious from
      // the call site even if the parent shape changes later.
      qc.invalidateQueries({ queryKey: queryKeys.properties.all })
      qc.invalidateQueries({ queryKey: queryKeys.properties.withStats() })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useUpdateProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Property> }) =>
      apiFetch<Property>(`/properties/${id}/`, { method: 'PATCH', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.properties.all })
      qc.invalidateQueries({ queryKey: queryKeys.properties.withStats() })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useDeleteProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/properties/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.properties.all })
      qc.invalidateQueries({ queryKey: queryKeys.properties.withStats() })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}
