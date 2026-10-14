// Deposit-movement hook tests: list/balance URLs and cascade invalidation.
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'

import {
  useDepositMovements,
  useDepositBalance,
  useCreateDepositMovement,
  useUpdateDepositMovement,
  useDeleteDepositMovement,
} from './deposits'
import { queryKeys } from './keys'
import { server } from '@/test/handlers'
import type { DepositMovement } from '@/types/deposit'

const API = '/api/v1'

const movement: DepositMovement = {
  id: 7,
  tenant: 3,
  date: '2026-10-01',
  kind: 'received',
  currency: 'EUR',
  amount: '1000.00',
  applied_to: null,
  transaction: null,
  owns_transaction: false,
  comment: null,
}

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function wrapperFor(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

function expectCascadeInvalidation(spy: ReturnType<typeof vi.spyOn>) {
  for (const key of [
    queryKeys.deposits.all,
    queryKeys.transactions.all,
    queryKeys.tenants.all,
    queryKeys.analytics.all,
  ]) {
    expect(spy).toHaveBeenCalledWith({ queryKey: key })
  }
}

describe('queryKeys.deposits', () => {
  it('nests byTenant and balance under all', () => {
    expect(queryKeys.deposits.byTenant(3).slice(0, 1)).toEqual(
      queryKeys.deposits.all,
    )
    expect(
      queryKeys.deposits.balance({ propertyId: 2 }).slice(0, 1),
    ).toEqual(queryKeys.deposits.all)
    expect(queryKeys.deposits.balance({ tenantId: 3 })).not.toEqual(
      queryKeys.deposits.balance({ tenantId: 4 }),
    )
  })
})

describe('useDepositMovements', () => {
  it('lists movements for a tenant', async () => {
    let url = ''
    server.use(
      http.get(`${API}/deposit-movements/`, ({ request }) => {
        url = new URL(request.url).search
        return HttpResponse.json([movement])
      }),
    )
    const { result } = renderHook(() => useDepositMovements(3), {
      wrapper: wrapperFor(makeClient()),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(url).toBe('?tenant=3')
    expect(result.current.data).toEqual([movement])
  })
})

describe('useDepositBalance', () => {
  it('requests balance by property with as_of', async () => {
    let url = ''
    const payload = {
      as_of: '2026-10-13',
      balances: [{ currency: 'EUR', amount: '1000.00' }],
      by_tenant: [{ tenant: 3, currency: 'EUR', amount: '1000.00' }],
    }
    server.use(
      http.get(`${API}/deposit-movements/balance/`, ({ request }) => {
        url = new URL(request.url).search
        return HttpResponse.json(payload)
      }),
    )
    const { result } = renderHook(
      () => useDepositBalance({ propertyId: 2, asOf: '2026-10-13' }),
      { wrapper: wrapperFor(makeClient()) },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(url).toBe('?property=2&as_of=2026-10-13')
    expect(result.current.data).toEqual(payload)
  })

  it('requests balance by tenant without as_of', async () => {
    let url = ''
    server.use(
      http.get(`${API}/deposit-movements/balance/`, ({ request }) => {
        url = new URL(request.url).search
        return HttpResponse.json({ as_of: '2026-10-14', balances: [] })
      }),
    )
    const { result } = renderHook(() => useDepositBalance({ tenantId: 3 }), {
      wrapper: wrapperFor(makeClient()),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(url).toBe('?tenant=3')
  })

  it('stays idle without a tenant or property', () => {
    const { result } = renderHook(() => useDepositBalance({}), {
      wrapper: wrapperFor(makeClient()),
    })
    expect(result.current.fetchStatus).toBe('idle')
  })
})

describe('deposit mutations', () => {
  it('create POSTs and invalidates the four key roots', async () => {
    let body: unknown
    server.use(
      http.post(`${API}/deposit-movements/`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(movement, { status: 201 })
      }),
    )
    const qc = makeClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useCreateDepositMovement(), {
      wrapper: wrapperFor(qc),
    })
    result.current.mutate({ tenant: 3, kind: 'received', amount: '1000.00' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(body).toEqual({ tenant: 3, kind: 'received', amount: '1000.00' })
    expectCascadeInvalidation(spy)
  })

  it('update PATCHes and invalidates the four key roots', async () => {
    let method = ''
    server.use(
      http.patch(`${API}/deposit-movements/:id/`, ({ request }) => {
        method = request.method
        return HttpResponse.json({ ...movement, amount: '900.00' })
      }),
    )
    const qc = makeClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useUpdateDepositMovement(), {
      wrapper: wrapperFor(qc),
    })
    result.current.mutate({ id: 7, data: { amount: '900.00' } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(method).toBe('PATCH')
    expectCascadeInvalidation(spy)
  })

  it('delete DELETEs and invalidates the four key roots', async () => {
    server.use(
      http.delete(
        `${API}/deposit-movements/:id/`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    )
    const qc = makeClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useDeleteDepositMovement(), {
      wrapper: wrapperFor(qc),
    })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expectCascadeInvalidation(spy)
  })
})
