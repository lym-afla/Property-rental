import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@/test/handlers'
import {
  propertyBreakdownSchema,
  isoDateSchema,
  portfolioCashFlowSchema,
  portfolioOccupancySchema,
  profitLossSchema,
  portfolioSummarySchema,
  propertyContributionSchema,
  propertyValuationSchema,
  propertyYieldsSchema,
  seriesDefinitionSchema,
  tenantRentPerformanceSchema,
  timeSeriesSchema,
} from '@/types/analytics'
import {
  usePropertyBreakdown,
  useExpenseDrivers,
  usePortfolioCashFlow,
  usePortfolioOccupancy,
  useProfitLoss,
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
    { key: 'rent', label: 'Rent', kind: 'income_category' },
    { key: 'total_income', label: 'Total income', kind: 'income_total' },
    { key: 'total_expenses', label: 'Total expenses', kind: 'expense_total' },
    { key: 'net_income', label: 'Net income', kind: 'net' },
    {
      key: 'cumulative_net_income',
      label: 'Cumulative net income',
      kind: 'cumulative',
    },
  ],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      rent: 1500,
      total_income: 1500,
      total_expenses: 0,
      net_income: 1500,
      cumulative_net_income: 1500,
    },
  ],
}

const expenseFixture = {
  ...cashFlowFixture,
  metric: 'expense_drivers',
  series: [{ key: 'utilities', label: 'Utilities', kind: 'expense_category' }],
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
      debt: null,
      equity: null,
      gross_yield: null,
      equity_yield: null,
      status: 'missing_valuation',
    },
  ],
}

const breakdownFixture = {
  ...cashFlowFixture,
  metric: 'property_breakdown',
  measure: 'property_value',
  measure_label: 'Property value',
  series: [
    { key: 'property_1', label: 'Alpha', kind: 'property' },
    {
      key: 'property_3',
      label: 'Gamma',
      kind: 'property',
    },
  ],
  points: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      property_1: 500000,
      property_3: null,
    },
  ],
  coverage: [
    {
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      property_id: 3,
      status: 'missing_currency',
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

const profitLossFixture = {
  metric: 'profit_and_loss',
  currency: 'GBP',
  scale: 1,
  end: '2026-07-29',
  columns: [
    { key: '2025', label: '2025', start: '2025-01-01', end: '2025-12-31' },
    { key: '2026', label: '2026', start: '2026-01-01', end: '2026-07-29' },
    { key: 'ytd', label: 'YTD', start: '2026-01-01', end: '2026-07-29' },
  ],
  rows: [
    { key: 'rent', label: 'Rent', kind: 'income', values: { '2025': 12000, '2026': 7000, ytd: 7000 } },
    { key: 'tax', label: 'Tax', kind: 'expense', values: { '2025': -1200, '2026': 0, ytd: 0 } },
    { key: 'total_revenue', label: 'Total revenue', kind: 'total_revenue', values: { '2025': 12000, '2026': 7000, ytd: 7000 } },
    { key: 'total_expenses', label: 'Total expenses', kind: 'total_expenses', values: { '2025': -1200, '2026': 0, ytd: 0 } },
    { key: 'net_income', label: 'Net income', kind: 'net_income', values: { '2025': 10800, '2026': 7000, ytd: 7000 } },
  ],
} as const

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('analytics runtime schemas', () => {
  it('accepts complete P&L rows and rejects missing or undeclared value keys', () => {
    expect(profitLossSchema.parse(profitLossFixture).rows[0].kind).toBe('income')
    expect(() => profitLossSchema.parse({
      ...profitLossFixture,
      rows: [{ ...profitLossFixture.rows[0], values: { '2025': 12000, ytd: 7000 } }],
    })).toThrow()
    expect(() => profitLossSchema.parse({
      ...profitLossFixture,
      rows: [{ ...profitLossFixture.rows[0], values: { ...profitLossFixture.rows[0].values, surprise: 1 } }],
    })).toThrow()
  })

  it('rejects P&L totals disguised as category rows and non-final YTD columns', () => {
    expect(() => profitLossSchema.parse({
      ...profitLossFixture,
      rows: [{ ...profitLossFixture.rows[2], kind: 'income' }],
    })).toThrow()
    expect(() => profitLossSchema.parse({
      ...profitLossFixture,
      columns: [profitLossFixture.columns[0], profitLossFixture.columns[2], profitLossFixture.columns[1]],
    })).toThrow()
  })

  it('rejects P&L statements with missing or duplicate mandatory totals', () => {
    expect(() => profitLossSchema.parse({
      ...profitLossFixture,
      rows: profitLossFixture.rows.filter((row) => row.kind !== 'net_income'),
    })).toThrow()
    expect(() => profitLossSchema.parse({
      ...profitLossFixture,
      rows: [...profitLossFixture.rows, profitLossFixture.rows[2]],
    })).toThrow()
  })

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

  it('rejects cash-flow responses missing chart-required aggregate series', () => {
    expect(() =>
      portfolioCashFlowSchema.parse({
        ...cashFlowFixture,
        series: cashFlowFixture.series.filter(
          (series) => series.key !== 'cumulative_net_income',
        ),
        points: cashFlowFixture.points.map(
          ({ cumulative_net_income: _omitted, ...point }) => point,
        ),
      }),
    ).toThrow()
  })

  it('rejects occupancy outside exact server invariants', () => {
    expect(() =>
      portfolioOccupancySchema.parse({
        ...occupancyFixture,
        points: [
          {
            ...occupancyFixture.points[0],
            occupied: 2,
            vacant: 1,
            occupancy_rate: 125,
          },
        ],
      }),
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

  it('rejects omitted, non-finite, and legacy yield denominator contracts', () => {
    const row = yieldsFixture.rows[0]
    const { equity: _equity, ...withoutEquity } = row
    const { equity_yield: _equityYield, ...withoutEquityYield } = row

    expect(() =>
      propertyYieldsSchema.parse({
        ...yieldsFixture,
        rows: [{ ...row, debt: Number.NaN }],
      }),
    ).toThrow()
    expect(() =>
      propertyYieldsSchema.parse({ ...yieldsFixture, rows: [withoutEquity] }),
    ).toThrow()
    expect(() =>
      propertyYieldsSchema.parse({
        ...yieldsFixture,
        rows: [{ ...withoutEquityYield, net_yield: null }],
      }),
    ).toThrow()
  })

  it.each([
    [0, 100000, 'zero_equity'],
    [-50000, 150000, 'negative_equity'],
  ])('accepts the explicit %s equity denominator status', (equity, debt, status) => {
    const parsed = propertyYieldsSchema.parse({
      ...yieldsFixture,
      rows: [{
        ...yieldsFixture.rows[0],
        property_value: 100000,
        debt,
        equity,
        gross_yield: 0,
        equity_yield: null,
        status,
      }],
    })

    expect(parsed.rows[0].status).toBe(status)
  })

  it('preserves null financial values and all issue arrays', () => {
    const summary = portfolioSummarySchema.parse(summaryFixture)
    const breakdown = propertyBreakdownSchema.parse(breakdownFixture)
    const valuation = propertyValuationSchema.parse(valuationFixture)
    const tenant = tenantRentPerformanceSchema.parse(tenantFixture)

    expect(summary.debt).toBeNull()
    expect(breakdown.points[0].property_3).toBeNull()
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

  it.each(['period_start', 'period_end', 'toString', 'constructor', '__proto__'])(
    'rejects dynamic series key collision %s',
    (key) => {
      expect(() =>
        timeSeriesSchema.parse({
          ...cashFlowFixture,
          series: [{ key, label: 'Collision', kind: 'income' }],
          points: [
            {
              period_start: '2026-01-01',
              period_end: '2026-01-31',
            },
          ],
        }),
      ).toThrow()
    },
  )

  it('requires exact property valuation series metadata', () => {
    expect(() =>
      propertyValuationSchema.parse({
        ...valuationFixture,
        series: [
          { key: 'market_value', label: 'Total value', kind: 'total' },
          ...valuationFixture.series.slice(1),
        ],
      }),
    ).toThrow()
  })

  it('requires exact tenant rent series metadata', () => {
    expect(() =>
      tenantRentPerformanceSchema.parse({
        ...tenantFixture,
        series: tenantFixture.series.map((series) =>
          series.key === 'received'
            ? { ...series, label: 'Collected rent' }
            : series,
        ),
      }),
    ).toThrow()
  })

  it('rejects year zero like the backend ISO date field', () => {
    expect(isoDateSchema.safeParse('0000-01-01').success).toBe(false)
  })

  it('rejects blank DRF CharField values', () => {
    expect(() =>
      seriesDefinitionSchema.parse({ key: 'rent', label: '   ', kind: 'income' }),
    ).toThrow()
    expect(() =>
      propertyContributionSchema.parse({
        ...contributionFixture,
        rows: [{ ...contributionFixture.rows[0], property_name: '\t' }],
      }),
    ).toThrow()
    expect(() =>
      propertyBreakdownSchema.parse({ ...breakdownFixture, measure_label: '' }),
    ).toThrow()
    expect(() =>
      propertyYieldsSchema.parse({
        ...yieldsFixture,
        rows: [{ ...yieldsFixture.rows[0], property_name: ' ' }],
      }),
    ).toThrow()
  })
})

describe('analytics query keys', () => {
  it('normalizes P&L property IDs and keys its period and currency', () => {
    const pnlFilters = { end: filters.end, currency: filters.currency, propertyIds: filters.propertyIds }
    expect(queryKeys.analytics.portfolio.profitLoss(pnlFilters)).toEqual(
      queryKeys.analytics.portfolio.profitLoss({ ...pnlFilters, propertyIds: [1, 3] }),
    )
    expect(queryKeys.analytics.portfolio.profitLoss(pnlFilters)).not.toEqual(
      queryKeys.analytics.portfolio.profitLoss({ ...pnlFilters, currency: 'USD' }),
    )
  })

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

  it('keys property breakdown measure and entity-specific filters', () => {
    expect(
      queryKeys.analytics.portfolio.propertyBreakdown({
        ...filters,
        measure: 'property_value',
      }),
    ).not.toEqual(
      queryKeys.analytics.portfolio.propertyBreakdown({
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
    expect(
      queryKeys.analytics.tenantRentPerformance(7, filters),
    ).toEqual([
      'analytics',
      'tenant-rent-performance',
      {
        tenantId: 7,
        start: filters.start,
        end: filters.end,
        grain: filters.grain,
        comparison: filters.comparison,
      },
    ])
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
      http.get('/api/v1/analytics/portfolio/property-breakdown/', () =>
        HttpResponse.json(breakdownFixture),
      ),
      http.get('/api/v1/analytics/portfolio/occupancy/', () =>
        HttpResponse.json(occupancyFixture),
      ),
      http.get('/api/v1/analytics/portfolio/profit-loss/', () =>
        HttpResponse.json(profitLossFixture),
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
      () => usePropertyBreakdown({ ...filters, measure: 'property_value' }),
      () => usePortfolioOccupancy(filters),
      () => useProfitLoss({ end: filters.end, currency: filters.currency, propertyIds: filters.propertyIds }),
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

  it('requests P&L with only its end, currency, and normalized property scope', async () => {
    let receivedSearch = ''
    server.use(
      http.get('/api/v1/analytics/portfolio/profit-loss/', ({ request }) => {
        receivedSearch = new URL(request.url).searchParams.toString()
        return HttpResponse.json(profitLossFixture)
      }),
    )

    const { result } = renderHook(
      () => useProfitLoss({ end: '2026-07-29', currency: 'GBP', propertyIds: [3, 1, 3] }),
      { wrapper: makeWrapper() },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(receivedSearch).toBe('end=2026-07-29&currency=GBP&property=1&property=3')
  })

  it('sends normalized repeated property filters and breakdown measure', async () => {
    let receivedSearch = ''
    server.use(
      http.get('/api/v1/analytics/portfolio/property-breakdown/', ({ request }) => {
        receivedSearch = new URL(request.url).searchParams.toString()
        return HttpResponse.json(breakdownFixture)
      }),
    )

    const { result } = renderHook(
      () => usePropertyBreakdown({ ...filters, measure: 'property_value' }),
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
      'start=2026-01-01&end=2026-07-29&grain=month',
    )
  })
})
