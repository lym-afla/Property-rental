import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { Loan, LoanCapitalisedFee, LoanCapitalisedFeeInput, LoanPayment, LoanProduct, LoanProductInput, LoanReconciliation } from '@/types/loan'
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

export function useLoanCapitalisedFees(loan: number) {
  return useQuery({
    queryKey: ['loans', loan, 'capitalised-fees'],
    queryFn: () => apiFetch<LoanCapitalisedFee[]>('/loan-capitalised-fees/', { query: { loan } }),
  })
}
export function useSaveLoanCapitalisedFee() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: LoanCapitalisedFeeInput) => apiFetch<LoanCapitalisedFee>(id ? `/loan-capitalised-fees/${id}/` : '/loan-capitalised-fees/', { method: id ? 'PATCH' : 'POST', body: data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loans'] }),
  })
}
export function useDeleteLoanCapitalisedFee() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/loan-capitalised-fees/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loans'] }),
  })
}

export function useLoanProducts(loan: number) {
  return useQuery({
    queryKey: ['loan-products', { loan }],
    queryFn: () => apiFetch<LoanProduct[]>('/loan-products/', { query: { loan } }),
  })
}
export function useSaveLoanProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: LoanProductInput) => apiFetch<LoanProduct>(id ? `/loan-products/${id}/` : '/loan-products/', { method: id ? 'PATCH' : 'POST', body: data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loan-products'] }),
  })
}
export function useDeleteLoanProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/loan-products/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['loan-products'] }),
  })
}

export function usePropertyLoanProducts(property: number) {
  return useQuery({
    queryKey: ['loan-products', { property }],
    queryFn: () => apiFetch<LoanProduct[]>('/loan-products/', { query: { property } }),
  })
}
