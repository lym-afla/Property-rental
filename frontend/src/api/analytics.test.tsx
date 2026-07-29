import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@/test/handlers'
import {
  currencyExposureSchema,
  portfolioSummarySchema,
  propertyValuationSchema,
  tenantRentPerformanceSchema,
  timeSeriesSchema,
} from '@/types/analytics'
import {
  useCurrencyExposure,
  useExpenseDrivers,
  usePortfolioCashFlow,
  usePortfolioOccupancy,
  usePortfolioSummary,
  usePropertyContribution,
  usePropertyValuationAnalytics,
  usePropertyYields,
  useTenantRentPerformance,
} from './analytics'
import { queryKeys } from './keys'

const filters = {
  start: '2026-01-01',
  end: '2026-07-29',
  currency: 'GBP',
  grain: 'month' as const,
  comparison: 'previous_period' as const,
  propertyIds: [3, 1, 3],
}

const cashFlowFixture = {
  metric: 'portfolio_cash_flow',
  grain: 'month',
  currency: 'GBP',
  scale: 1,
  start: '2026-01-01',
  end: '2026-07-29',
  series: [
    { key: 'rent', label: 'Rent', kind: 'income' },
    { key: 'net_income', label: 'Net income', kind: 'net' },
  ],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      rent: 1500,
      net_income: 1500,
    },
  ],
}

const expenseFixture = {
  ...cashFlowFixture,
  metric: 'expense_drivers',
  series: [{ key: 'utilities', label: 'Utilities', kind: 'expense' }],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      utilities: -250,
    },
  ],
}

const occupancyFixture = {
  ...cashFlowFixture,
  metric: 'portfolio_occupancy',
  currency: null,
  series: [
    { key: 'capacity', label: 'Capacity', kind: 'capacity' },
    { key: 'occupied', label: 'Occupied', kind: 'occupied' },
    { key: 'vacant', label: 'Vacant', kind: 'vacant' },
    { key: 'occupancy_rate', label: 'Occupancy rate', kind: 'percentage' },
  ],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      capacity: 2,
      occupied: 1,
      vacant: 1,
      occupancy_rate: 50,
    },
  ],
}

const summaryFixture = {
  currency: 'GBP',
  scale: 1,
  start: '2026-01-01',
  end: '2026-07-29',
  property_count: 2,
  rental_inventory_count: 2,
  occupied: 1,
  occupancy_rate: 50,
  revenue: 1500,
  costs: 250,
  net_income: 1250,
  property_value: 500000,
  debt: null,
  equity: null,
  valuation_status: 'missing_valuation',
  property_value_status: 'ok',
  debt_status: 'missing_valuation',
}

const contributionFixture = {
  metric: 'property_contribution',
  currency: 'GBP',
  scale: 1,
  start: '2026-01-01',
  end: '2026-07-29',
  portfolio_net_income: 1250,
  rows: [
    {
      property_id: 1,
      property_name: 'Alpha',
      revenue: 1500,
      costs: 250,
      net_income: 1250,
      portfolio_share: 100,
    },
  ],
}

const yieldsFixture = {
  metric: 'property_yields',
  currency: 'GBP',
  scale: 1,
  start: '2026-01-01',
  end: '2026-07-29',
  rows: [
    {
      property_id: 1,
      property_name: 'Alpha',
      valuation_date: null,
      property_value: null,
      annualized_revenue: 2737.5,
      annualized_costs: 456.25,
      gross_yield: null,
      net_yield: null,
      status: 'missing_valuation',
    },
  ],
}

const exposureFixture = {
  ...cashFlowFixture,
  metric: 'currency_exposure',
  measure: 'property_value',
  measure_label: 'Property value',
  series: [
    { key: 'GBP', label: 'GBP', kind: 'native_currency' },
    {
      key: 'missing_currency',
      label: 'Missing native currency',
      kind: 'native_currency',
    },
  ],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      GBP: 500000,
      missing_currency: null,
    },
  ],
  coverage: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      currency: null,
      status: 'missing_currency',
      missing_count: 1,
      stale_count: 0,
    },
  ],
}

const valuationFixture = {
  metric: 'property_valuation',
  grain: 'record',
  currency: null,
  scale: 1,
  start: '2026-01-01',
  end: '2026-07-29',
  status: 'missing_currency',
  series: [
    { key: 'total_value', label: 'Total value', kind: 'total' },
    { key: 'debt', label: 'Debt', kind: 'debt' },
    { key: 'equity', label: 'Equity', kind: 'equity' },
  ],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-01',
      total_value: 500000,
      debt: null,
      equity: null,
      status: 'missing_debt',
    },
  ],
}

const tenantFixture = {
  metric: 'tenant_rent_performance',
  grain: 'month',
  currency: 'GBP',
  scale: 1,
  start: '2026-01-01',
  end: '2026-07-29',
  opening_arrears: null,
  opening_issues: ['missing_rent_rate', 'incomplete_opening_history'],
  status: 'partial_data',
  issues: [
    'missing_rent_rate',
    'missing_received_fx',
    'incomplete_opening_history',
  ],
  series: [
    { key: 'expected', label: 'Expected rent', kind: 'expected' },
    { key: 'received', label: 'Received rent', kind: 'received' },
    { key: 'variance', label: 'Variance', kind: 'variance' },
    {
      key: 'cumulative_arrears',
      label: 'Cumulative arrears',
      kind: 'cumulative',
    },
  ],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      expected: 1000,
      received: null,
      variance: null,
      cumulative_arrears: null,
      status: 'incomplete_history',
      issues: ['missing_received_fx', 'incomplete_opening_history'],
    },
  ],
}

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('analytics runtime schemas', () => {
  it('accepts raw ISO-bounded time series', () => {
    expect(timeSeriesSchema.parse(cashFlowFixture).metric).toBe(
      'portfolio_cash_flow',
    )
  })

  it('rejects scaled monetary responses', () => {
    expect(() =>
      timeSeriesSchema.parse({ ...cashFlowFixture, scale: 1000 }),
    ).toThrow()
  })

  it('rejects malformed dates, undeclared fields, and point keys', () => {
    expect(() =>
      timeSeriesSchema.parse({ ...cashFlowFixture, start: '2026-02-30' }),
    ).toThrow()
    expect(() =>
      portfolioSummarySchema.parse({ ...summaryFixture, surprise: true }),
    ).toThrow()
    expect(() =>
      timeSeriesSchema.parse({
        ...cashFlowFixture,
        points: [{ ...cashFlowFixture.points[0], client_total: 1500 }],
      }),
    ).toThrow()
  })

  it('preserves null financial values and all issue arrays', () => {
    const summary = portfolioSummarySchema.parse(summaryFixture)
    const exposure = currencyExposureSchema.parse(exposureFixture)
    const valuation = propertyValuationSchema.parse(valuationFixture)
    const tenant = tenantRentPerformanceSchema.parse(tenantFixture)

    expect(summary.debt).toBeNull()
    expect(exposure.points[0].missing_currency).toBeNull()
    expect(valuation.points[0].debt).toBeNull()
    expect(tenant.opening_issues).toEqual([
      'missing_rent_rate',
      'incomplete_opening_history',
    ])
    expect(tenant.points[0].issues).toEqual([
      'missing_received_fx',
      'incomplete_opening_history',
    ])
  })
})

describe('analytics query keys', () => {
  it('normalizes repeated property IDs without losing data filters', () => {
    expect(queryKeys.analytics.portfolio.cashFlow(filters)).toEqual(
      queryKeys.analytics.portfolio.cashFlow({
        ...filters,
        propertyIds: [1, 3],
      }),
    )

    const base = queryKeys.analytics.portfolio.cashFlow(filters)
    for (const changed of [
      { ...filters, start: '2026-02-01' },
      { ...filters, end: '2026-06-30' },
      { ...filters, currency: 'USD' },
      { ...filters, grain: 'quarter' as const },
      { ...filters, comparison: null },
      { ...filters, propertyIds: [1] },
    ]) {
      expect(queryKeys.analytics.portfolio.cashFlow(changed)).not.toEqual(base)
    }
  })

  it('keys exposure measure and entity-specific filters', () => {
    expect(
      queryKeys.analytics.portfolio.currencyExposure({
        ...filters,
        measure: 'property_value',
      }),
    ).not.toEqual(
      queryKeys.analytics.portfolio.currencyExposure({
        ...filters,
        measure: 'debt',
      }),
    )
    expect(queryKeys.analytics.propertyValuation(7, '2026-07-29')).not.toEqual(
      queryKeys.analytics.propertyValuation(7, '2026-06-30'),
    )
    expect(
      queryKeys.analytics.tenantRentPerformance(7, filters),
    ).not.toEqual(queryKeys.analytics.tenantRentPerformance(8, filters))
  })
})

describe('analytics hooks', () => {
  it('validates every Tasks 1-4 analytics endpoint before exposing data', async () => {
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', () =>
        HttpResponse.json(summaryFixture),
      ),
      http.get('/api/v1/analytics/portfolio/cash-flow/', () =>
        HttpResponse.json(cashFlowFixture),
      ),
      http.get('/api/v1/analytics/portfolio/expenses/', () =>
        HttpResponse.json(expenseFixture),
      ),
      http.get('/api/v1/analytics/portfolio/property-contribution/', () =>
        HttpResponse.json(contributionFixture),
      ),
      http.get('/api/v1/analytics/portfolio/yields/', () =>
        HttpResponse.json(yieldsFixture),
      ),
      http.get('/api/v1/analytics/portfolio/currency-exposure/', () =>
        HttpResponse.json(exposureFixture),
      ),
      http.get('/api/v1/analytics/portfolio/occupancy/', () =>
        HttpResponse.json(occupancyFixture),
      ),
      http.get('/api/v1/analytics/properties/7/valuation/', () =>
        HttpResponse.json(valuationFixture),
      ),
      http.get('/api/v1/analytics/tenants/9/rent-performance/', () =>
        HttpResponse.json(tenantFixture),
      ),
    )

    const hooks = [
      () => usePortfolioSummary(filters),
      () => usePortfolioCashFlow(filters),
      () => useExpenseDrivers(filters),
      () => usePropertyContribution(filters),
      () => usePropertyYields(filters),
      () => useCurrencyExposure({ ...filters, measure: 'property_value' }),
      () => usePortfolioOccupancy(filters),
      () => usePropertyValuationAnalytics(7, '2026-07-29'),
      () => useTenantRentPerformance(9, filters),
    ]

    for (const useAnalyticsHook of hooks) {
      const { result, unmount } = renderHook(() => useAnalyticsHook(), {
        wrapper: makeWrapper(),
      })
      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(result.current.data?.scale).toBe(1)
      unmount()
    }
  })

  it('surfaces a contract error instead of malformed cash-flow data', async () => {
    server.use(
      http.get('/api/v1/analytics/portfolio/cash-flow/', () =>
        HttpResponse.json({ ...cashFlowFixture, scale: 1000 }),
      ),
    )

    const { result } = renderHook(() => usePortfolioCashFlow(filters), {
      wrapper: makeWrapper(),
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })

  it('sends normalized repeated property filters and exposure measure', async () => {
    let receivedSearch = ''
    server.use(
      http.get('/api/v1/analytics/portfolio/currency-exposure/', ({ request }) => {
        receivedSearch = new URL(request.url).searchParams.toString()
        return HttpResponse.json(exposureFixture)
      }),
    )

    const { result } = renderHook(
      () => useCurrencyExposure({ ...filters, measure: 'property_value' }),
      { wrapper: makeWrapper() },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(receivedSearch).toBe(
      'start=2026-01-01&end=2026-07-29&currency=GBP&grain=month&property=1&property=3&measure=property_value',
    )
    expect(receivedSearch).not.toContain('comparison')
  })

  it('does not send portfolio-only property or comparison state to tenant analytics', async () => {
    let receivedSearch = ''
    server.use(
      http.get(
        '/api/v1/analytics/tenants/9/rent-performance/',
        ({ request }) => {
          receivedSearch = new URL(request.url).searchParams.toString()
          return HttpResponse.json(tenantFixture)
        },
      ),
    )

    const { result } = renderHook(
      () => useTenantRentPerformance(9, filters),
      { wrapper: makeWrapper() },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(receivedSearch).toBe(
      'start=2026-01-01&end=2026-07-29&currency=GBP&grain=month',
    )
  })
})
