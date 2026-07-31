// Centralized React Query key factory (spec §5.2).
//
// One namespace per entity, each exposing the factories it needs. Mutations
// invalidate via these factories so the cascade rules
// (properties -> properties/with_stats) live in
// the hooks rather than scattered across pages.
//
// Every key tuple ends with a primitive or a stable object so React Query can
// deep-compare keys across renders (no inline `[]` literals that would break
// referential equality).

type TransactionFilters = {
  property?: number
  tenant?: number
  category?: string
  type?: string
  // ISO month `YYYY-MM` or ISO date `YYYY-MM-DD`.
  start?: string
  end?: string
  currency?: string
}

type AnalyticsFilters = {
  start?: string
  end?: string
  currency?: string
  grain?: 'month' | 'quarter' | 'year'
  comparison?: 'previous_period' | null
  propertyIds?: readonly number[]
}

type PropertyBreakdownFilters = AnalyticsFilters & {
  measure: 'property_value' | 'equity' | 'debt' | 'rental_income'
}

function normalizePropertyIds(propertyIds: readonly number[] = []): number[] {
  return [...new Set(propertyIds)].sort((left, right) => left - right)
}

function normalizeAnalyticsFilters(filters: AnalyticsFilters) {
  return {
    start: filters.start,
    end: filters.end,
    currency: filters.currency,
    grain: filters.grain,
    comparison: filters.comparison,
    propertyIds: normalizePropertyIds(filters.propertyIds),
  }
}

export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },

  properties: {
    all: ['properties'] as const,
    // Include `asOf` + `currency` in the cache key so the same component
    // tree can hold multiple with_stats responses (e.g. one in USD for the
    // list page, one in native currency for a detail page, one at a
    // different as-of date for the Currency Exposure chart) without one
    // clobbering the other. Mutations still invalidate via the `all`
    // parent key, so all variants refetch together.
    withStats: (asOf?: string, currency?: string) =>
      ['properties', 'with-stats', { asOf, currency }] as const,
    detail: (id: number) => ['properties', 'detail', id] as const,
  },

  tenants: {
    all: ['tenants'] as const,
    // Include `asOf` + `currency` in the cache key so the same component
    // tree can hold multiple with_stats responses (e.g. one in USD for
    // the list page, one in native currency for a detail page) without
    // one clobbering the other. Mutations still invalidate via the
    // `all` parent key, so all variants refetch together.
    withStats: (asOf?: string, currency?: string) =>
      ['tenants', 'with-stats', { asOf, currency }] as const,
    detail: (id: number) => ['tenants', 'detail', id] as const,
  },

  transactions: {
    all: ['transactions'] as const,
    // Used both as the root key (for invalidation) and to scope a list query
    // by arbitrary filters. Pages call `queryKeys.transactions.filtered({
    // property, ... })`; mutations invalidate via the `all` factory.
    filtered: (filters: TransactionFilters) =>
      ['transactions', 'filtered', filters] as const,
    detail: (id: number) => ['transactions', 'detail', id] as const,
  },

  fx: {
    all: ['fx'] as const,
    detail: (id: number) => ['fx', 'detail', id] as const,
  },

  propertyValuations: {
    all: ['property-valuations'] as const,
    byProperty: (propertyId: number) =>
      ['property-valuations', 'by-property', propertyId] as const,
    detail: (id: number) => ['property-valuations', 'detail', id] as const,
  },

  leaseRents: {
    all: ['lease-rents'] as const,
    byTenant: (tenantId: number) =>
      ['lease-rents', 'by-tenant', tenantId] as const,
    detail: (id: number) => ['lease-rents', 'detail', id] as const,
  },

  analytics: {
    all: ['analytics'] as const,
    portfolio: {
      all: ['analytics', 'portfolio'] as const,
      summary: (filters: AnalyticsFilters) =>
        [
          'analytics',
          'portfolio',
          'summary',
          normalizeAnalyticsFilters(filters),
        ] as const,
      cashFlow: (filters: AnalyticsFilters) =>
        [
          'analytics',
          'portfolio',
          'cash-flow',
          normalizeAnalyticsFilters(filters),
        ] as const,
      expenseDrivers: (filters: AnalyticsFilters) =>
        [
          'analytics',
          'portfolio',
          'expense-drivers',
          normalizeAnalyticsFilters(filters),
        ] as const,
      profitLoss: (filters: AnalyticsFilters) =>
        [
          'analytics',
          'portfolio',
          'profit-loss',
          normalizeAnalyticsFilters(filters),
        ] as const,
      propertyContribution: (filters: AnalyticsFilters) =>
        [
          'analytics',
          'portfolio',
          'property-contribution',
          normalizeAnalyticsFilters(filters),
        ] as const,
      propertyYields: (filters: AnalyticsFilters) =>
        [
          'analytics',
          'portfolio',
          'yields',
          normalizeAnalyticsFilters(filters),
        ] as const,
      propertyBreakdown: (filters: PropertyBreakdownFilters) =>
        [
          'analytics',
          'portfolio',
          'property-breakdown',
          { ...normalizeAnalyticsFilters(filters), measure: filters.measure },
        ] as const,
      occupancy: (filters: AnalyticsFilters) =>
        [
          'analytics',
          'portfolio',
          'occupancy',
          normalizeAnalyticsFilters(filters),
        ] as const,
    },
    propertyValuation: (propertyId: number, end?: string) =>
      ['analytics', 'property-valuation', { propertyId, end }] as const,
    tenantRentPerformance: (
      tenantId: number,
      filters: Pick<
        AnalyticsFilters,
        'start' | 'end' | 'grain' | 'comparison'
      >,
    ) =>
      [
        'analytics',
        'tenant-rent-performance',
        {
          tenantId,
          start: filters.start,
          end: filters.end,
          grain: filters.grain,
          comparison: filters.comparison,
        },
      ] as const,
  },
}

export { normalizePropertyIds }
export type { AnalyticsFilters, PropertyBreakdownFilters, TransactionFilters }
