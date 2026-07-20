import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { Tenant, TenantWithStats } from '@/types/tenant'

// React Query hooks for the `/api/v1/tenants/` ViewSet (Task 17).
//
// Cascade invalidation: every tenant mutation touches BOTH `tenants.all` AND
// `tenants.withStats` — the with_stats endpoint joins on Transaction and
// recomputes rent_rate / debt, so any change to a tenant (or its underlying
// transactions) makes those aggregated numbers stale.
//
// The `vacate` action sets `lease_end` server-side; once that fires the
// tenant's stats row would report "Tenant vacated", so it also invalidates
// the with_stats view.

export function useTenants() {
  return useQuery<Tenant[]>({
    queryKey: queryKeys.tenants.all,
    queryFn: () => apiFetch<Tenant[]>('/tenants/'),
  })
}

export function useTenantsWithStats(asOf?: string, currency?: string) {
  return useQuery<TenantWithStats[]>({
    queryKey: queryKeys.tenants.withStats,
    queryFn: () =>
      apiFetch<TenantWithStats[]>('/tenants/with_stats/', {
        query: { as_of: asOf, currency },
      }),
  })
}

export function useTenant(id: number) {
  return useQuery<Tenant>({
    queryKey: queryKeys.tenants.detail(id),
    queryFn: () => apiFetch<Tenant>(`/tenants/${id}/`),
  })
}

export function useCreateTenant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Tenant>) =>
      apiFetch<Tenant>('/tenants/', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.tenants.withStats })
    },
  })
}

export function useUpdateTenant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Tenant> }) =>
      apiFetch<Tenant>(`/tenants/${id}/`, { method: 'PATCH', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.tenants.withStats })
    },
  })
}

export function useDeleteTenant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/tenants/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.tenants.withStats })
    },
  })
}

// POST /tenants/<id>/vacate/ body `{ lease_end }` -> 200 full Tenant.
// See `TenantViewSet.vacate` in `rentals/api/views.py`: it returns
// `Response(TenantSerializer(tenant).data)` — the whole serialized tenant,
// not a `{detail, lease_end}` envelope.
export function useVacateTenant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, leaseEnd }: { id: number; leaseEnd: string }) =>
      apiFetch<Tenant>(
        `/tenants/${id}/vacate/`,
        { method: 'POST', body: { lease_end: leaseEnd } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.tenants.withStats })
    },
  })
}
