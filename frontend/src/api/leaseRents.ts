import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { LeaseRent } from '@/types/leaseRent'

// React Query hooks for the `/api/v1/lease-rents/` ViewSet.
//
// Backs the tenant detail page's "Update rent" dialog: POST creates a new
// effective-date rent entry on the tenant's `Lease_rent` history. The
// current rent rate is already aggregated into `TenantWithStats.rent_rate`
// (via `Tenant.lease_rent` on the backend), so the list hook is keyed by
// tenant for future history views but the create-hook is the primary
// entry point today.
//
// Cascade invalidation: every lease-rent mutation invalidates BOTH
// `leaseRents.all` AND `tenants.all` — the tenants `with_stats` endpoint
// recomputes `rent_rate` from `Lease_rent`, so any change to the
// underlying history immediately makes the cached rent rate stale.

export function useLeaseRents(tenantId: number) {
  return useQuery<LeaseRent[]>({
    queryKey: queryKeys.leaseRents.byTenant(tenantId),
    queryFn: () =>
      apiFetch<LeaseRent[]>('/lease-rents/', {
        query: { tenant: tenantId },
      }),
  })
}

export function useLeaseRent(id: number) {
  return useQuery<LeaseRent>({
    queryKey: queryKeys.leaseRents.detail(id),
    queryFn: () => apiFetch<LeaseRent>(`/lease-rents/${id}/`),
  })
}

export function useCreateLeaseRent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<LeaseRent>) =>
      apiFetch<LeaseRent>('/lease-rents/', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.leaseRents.all })
      // Tenant stats recompute `rent_rate` from `Lease_rent`, so any
      // write here makes the cached tenant rows (including the
      // `with_stats` aggregates) stale.
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useUpdateLeaseRent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<LeaseRent> }) =>
      apiFetch<LeaseRent>(`/lease-rents/${id}/`, {
        method: 'PATCH',
        body: data,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.leaseRents.all })
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useDeleteLeaseRent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/lease-rents/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.leaseRents.all })
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}
