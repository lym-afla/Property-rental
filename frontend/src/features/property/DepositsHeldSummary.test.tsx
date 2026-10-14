import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { DepositsHeldSummary } from './DepositsHeldSummary'

type Balance = {
  as_of: string
  balances: { currency: string; amount: string }[]
  by_tenant?: { tenant: number; currency: string; amount: string }[]
}

const mocks = vi.hoisted(() => ({
  query: {
    data: undefined as Balance | undefined,
    isLoading: false,
    isError: false,
  },
  useDepositBalance: vi.fn(),
}))

vi.mock('@/api/deposits', () => ({
  useDepositBalance: (params: unknown) => {
    mocks.useDepositBalance(params)
    return mocks.query
  },
}))

const tenants = [
  { id: 1, name: 'Alice Smith' },
  { id: 2, name: 'Bob Jones' },
]

function renderSummary() {
  return render(
    <MemoryRouter>
      <DepositsHeldSummary propertyId={5} asOf="2026-07-29" tenants={tenants} />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mocks.query = { data: undefined, isLoading: false, isError: false }
  mocks.useDepositBalance.mockClear()
})

describe('DepositsHeldSummary', () => {
  it('queries by property and as-of date', () => {
    renderSummary()
    expect(mocks.useDepositBalance).toHaveBeenCalledWith({
      propertyId: 5,
      asOf: '2026-07-29',
    })
  })

  it('lists per-tenant lines linking to the tenant page, then the total', () => {
    mocks.query.data = {
      as_of: '2026-07-29',
      balances: [{ currency: 'EUR', amount: '1500.00' }],
      by_tenant: [
        { tenant: 1, currency: 'EUR', amount: '1000.00' },
        { tenant: 2, currency: 'EUR', amount: '500.00' },
      ],
    }
    renderSummary()
    expect(screen.getByText('Deposits held')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alice Smith' })).toHaveAttribute(
      'href',
      '/tenants/1',
    )
    expect(screen.getByRole('link', { name: 'Bob Jones' })).toHaveAttribute(
      'href',
      '/tenants/2',
    )
    const aliceRow = screen.getByRole('link', { name: 'Alice Smith' }).closest('li')!
    expect(aliceRow).toHaveTextContent('€1,000')
    const total = screen.getByText('Total').closest('li')!
    expect(total).toHaveTextContent('€1,500')
  })

  it('shows one total line per currency', () => {
    mocks.query.data = {
      as_of: '2026-07-29',
      balances: [
        { currency: 'EUR', amount: '1000.00' },
        { currency: 'USD', amount: '250.00' },
      ],
      by_tenant: [
        { tenant: 1, currency: 'EUR', amount: '1000.00' },
        { tenant: 2, currency: 'USD', amount: '250.00' },
      ],
    }
    renderSummary()
    const totals = screen.getAllByText('Total')
    expect(totals).toHaveLength(2)
    expect(totals[0].closest('li')).toHaveTextContent('€1,000')
    expect(totals[1].closest('li')).toHaveTextContent('$250')
  })

  it('still shows zero balances', () => {
    mocks.query.data = {
      as_of: '2026-07-29',
      balances: [{ currency: 'EUR', amount: '0.00' }],
      by_tenant: [{ tenant: 1, currency: 'EUR', amount: '0.00' }],
    }
    renderSummary()
    const alice = screen.getByRole('link', { name: 'Alice Smith' }).closest('li')!
    expect(within(alice).getByText('€0')).toBeInTheDocument()
    expect(screen.getByText('Total').closest('li')).toHaveTextContent('€0')
  })

  it('falls back to Tenant #id for unknown tenants', () => {
    mocks.query.data = {
      as_of: '2026-07-29',
      balances: [{ currency: 'EUR', amount: '100.00' }],
      by_tenant: [{ tenant: 99, currency: 'EUR', amount: '100.00' }],
    }
    renderSummary()
    expect(screen.getByRole('link', { name: 'Tenant #99' })).toHaveAttribute(
      'href',
      '/tenants/99',
    )
  })

  it('renders nothing when balances is empty', () => {
    mocks.query.data = { as_of: '2026-07-29', balances: [], by_tenant: [] }
    const { container } = renderSummary()
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing while loading or on error', () => {
    mocks.query.isLoading = true
    const first = renderSummary()
    expect(first.container).toBeEmptyDOMElement()
    first.unmount()
    mocks.query = { data: undefined, isLoading: false, isError: true }
    const second = renderSummary()
    expect(second.container).toBeEmptyDOMElement()
  })
})
