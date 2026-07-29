import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys, type TransactionFilters } from './keys'
import type { Transaction } from '@/types/transaction'

// React Query hooks for the `/api/v1/transactions/` ViewSet (Task 17).
//
// Every transaction mutation invalidates the transaction list cache.

export function useTransactions(filters: TransactionFilters = {}) {
  return useQuery<Transaction[]>({
    queryKey: queryKeys.transactions.filtered(filters),
    queryFn: () =>
      apiFetch<Transaction[]>('/transactions/', {
        query: {
          property: filters.property,
          tenant: filters.tenant,
          category: filters.category,
          type: filters.type,
          // Backend reads ``from`` / ``to`` (the same keys the
          // TransactionsPage URL uses). The previous code sent
          // ``start``/``end`` which the ViewSet never filtered on, so
          // the date range filter silently no-op'd.
          from: filters.start,
          to: filters.end,
          currency: filters.currency,
        },
      }),
  })
}

export function useTransaction(id: number) {
  return useQuery<Transaction>({
    queryKey: queryKeys.transactions.detail(id),
    queryFn: () => apiFetch<Transaction>(`/transactions/${id}/`),
  })
}

export function useCreateTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Transaction>) =>
      apiFetch<Transaction>('/transactions/', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.transactions.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useUpdateTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Transaction> }) =>
      apiFetch<Transaction>(`/transactions/${id}/`, {
        method: 'PATCH',
        body: data,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.transactions.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}

export function useDeleteTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/transactions/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.transactions.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}
