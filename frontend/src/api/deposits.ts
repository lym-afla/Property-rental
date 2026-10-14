import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys, type DepositBalanceParams } from './keys'
import type { DepositBalance, DepositMovement } from '@/types/deposit'

// React Query hooks for the `/api/v1/deposit-movements/` ViewSet.
//
// Cascade invalidation: a deposit movement can create/update/delete a linked
// transaction (rent or cost reimbursement), and feeds tenant stats and
// cash-flow analytics, so every mutation invalidates deposits, transactions,
// tenants and analytics.

export function useDepositMovements(tenantId: number) {
  return useQuery<DepositMovement[]>({
    queryKey: queryKeys.deposits.byTenant(tenantId),
    queryFn: () =>
      apiFetch<DepositMovement[]>('/deposit-movements/', {
        query: { tenant: tenantId },
      }),
  })
}

export function useDepositBalance(params: DepositBalanceParams) {
  const { tenantId, propertyId, asOf } = params
  return useQuery<DepositBalance>({
    queryKey: queryKeys.deposits.balance(params),
    queryFn: () =>
      apiFetch<DepositBalance>('/deposit-movements/balance/', {
        query: { tenant: tenantId, property: propertyId, as_of: asOf },
      }),
    enabled: tenantId !== undefined || propertyId !== undefined,
  })
}

function useInvalidateDepositCascade() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: queryKeys.deposits.all })
    qc.invalidateQueries({ queryKey: queryKeys.transactions.all })
    qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
    qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
  }
}

export function useCreateDepositMovement() {
  const invalidate = useInvalidateDepositCascade()
  return useMutation({
    mutationFn: (data: Partial<DepositMovement>) =>
      apiFetch<DepositMovement>('/deposit-movements/', {
        method: 'POST',
        body: data,
      }),
    onSuccess: invalidate,
  })
}

export function useUpdateDepositMovement() {
  const invalidate = useInvalidateDepositCascade()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<DepositMovement> }) =>
      apiFetch<DepositMovement>(`/deposit-movements/${id}/`, {
        method: 'PATCH',
        body: data,
      }),
    onSuccess: invalidate,
  })
}

export function useDeleteDepositMovement() {
  const invalidate = useInvalidateDepositCascade()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/deposit-movements/${id}/`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })
}
