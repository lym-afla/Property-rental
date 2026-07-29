// Task 13 — React Query hook tests for FX.
//
// Covers query hooks (`useFX`) and mutation hooks (`useCreateFX`,
// `useUpdateFXRate`, `useDeleteFX`, `useUpdateFX`). `useUpdateFX` /
// `useUpdateFXRate` cascades to `fx.all` and `transactions`;
// the create/delete hooks only invalidate `fx.all`.
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import {
  useFX,
  useCreateFX,
  useUpdateFXRate,
  useDeleteFX,
  useUpdateFX,
} from './fx'
import { queryKeys } from './keys'
import { fixtureFX } from '@/__fixtures__/fx'

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

describe('useFX', () => {
  it('returns the FX list', async () => {
    const { result } = renderHook(() => useFX(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBe(2)
    expect(result.current.data?.[0].id).toBe(fixtureFX.id)
  })
})

describe('useCreateFX', () => {
  it('POSTs and invalidates fx.all', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useCreateFX(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ from_currency: 'EUR', to_currency: 'USD', rate: '1.1' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.id).toBe(999)
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.fx.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.analytics.all,
    })
  })
})

describe('useUpdateFXRate', () => {
  it('PATCHes and invalidates fx + transactions', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useUpdateFXRate(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ id: fixtureFX.id, data: { rate: '1.2500' } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.rate).toBe('1.2500')
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.fx.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.transactions.all,
    })
  })
})

describe('useDeleteFX', () => {
  it('DELETEs and invalidates fx.all', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useDeleteFX(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate(fixtureFX.id)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.fx.all,
    })
  })
})

describe('useUpdateFX', () => {
  it('POSTs to /fx/update/ and invalidates fx + transactions', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useUpdateFX(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate()
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.detail).toBe('FX rates updated')
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.fx.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.transactions.all,
    })
  })
})
