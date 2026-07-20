// Task 13 — React Query hook tests for transactions.
//
// Covers query hooks (`useTransactions`, `useTransaction`) and mutation
// hooks (`useCreateTransaction`, `useUpdateTransaction`, `useDeleteTransaction`).
// Every mutation asserts endpoint success AND the cascade invalidation
// (`transactions.all` + `chart-data`).
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import {
  useTransactions,
  useTransaction,
  useCreateTransaction,
  useUpdateTransaction,
  useDeleteTransaction,
} from './transactions'
import { queryKeys } from './keys'
import { fixtureTransactionIncome } from '@/__fixtures__/transaction'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

function makeWrapperWithClient(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

describe('useTransactions', () => {
  it('returns the transaction list', async () => {
    const { result } = renderHook(() => useTransactions(), {
      wrapper: makeWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBe(2)
    expect(result.current.data?.[0].id).toBe(fixtureTransactionIncome.id)
  })
})

describe('useTransaction', () => {
  it('returns a single transaction by id', async () => {
    const { result } = renderHook(
      () => useTransaction(fixtureTransactionIncome.id),
      { wrapper: makeWrapper() },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.amount).toBe(fixtureTransactionIncome.amount)
  })
})

describe('useCreateTransaction', () => {
  it('POSTs and invalidates transactions + chart-data keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useCreateTransaction(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ amount: '500.00', property: 1 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.id).toBe(999)
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.transactions.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.chartData.all,
    })
  })
})

describe('useUpdateTransaction', () => {
  it('PATCHes and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useUpdateTransaction(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({
      id: fixtureTransactionIncome.id,
      data: { amount: '999.99' },
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.amount).toBe('999.99')
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.transactions.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.chartData.all,
    })
  })
})

describe('useDeleteTransaction', () => {
  it('DELETEs and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useDeleteTransaction(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate(fixtureTransactionIncome.id)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.transactions.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.chartData.all,
    })
  })
})
