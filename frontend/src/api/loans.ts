import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { Loan, LoanPayment, LoanReconciliation } from '@/types/loan'
import type { Transaction } from '@/types/transaction'

export function useLoans(property?: number) {
  return useQuery({
    queryKey: ['loans', { property }],
    queryFn: () => apiFetch<Loan[]>('/loans/', { query: { property } }),
  })
}
export function useLoanReconciliation(id: number) {
  return useQuery({
    queryKey: ['loans', id, 'reconciliation'],
    queryFn: () => apiFetch<LoanReconciliation[]>(`/loans/${id}/reconciliation/`),
  })
}
export function useSaveLoan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Loan>) => apiFetch<Loan>(id ? `/loans/${id}/` : '/loans/', { method: id ? 'PATCH' : 'POST', body: data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loans'] }),
  })
}
export function useLoanPayment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: LoanPayment }) => apiFetch<Transaction[]>(`/loans/${id}/payments/`, { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['loans'] })
      qc.invalidateQueries({ queryKey: queryKeys.transactions.all })
      qc.invalidateQueries({ queryKey: queryKeys.analytics.all })
    },
  })
}
