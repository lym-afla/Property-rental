// Centralized React Query key factory (spec §5.2).
//
// One namespace per entity, each exposing the factories it needs. Mutations
// invalidate via these factories so the cascade rules
// (transactions -> chart-data, properties -> properties/with_stats) live in
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

  // Charts derive from transactions, so any transaction mutation must also
  // invalidate `chart-data`. The shape mirrors the ChartDataView query
  // params (spec §5.2): `{ type, id, freq, start, end, currency }`.
  chartData: {
    all: ['chart-data'] as const,
    filtered: (filters: {
      type: string
      id: number | string
      freq?: string
      start?: string
      end?: string
      currency?: string
    }) => ['chart-data', 'filtered', filters] as const,
  },
}

export type { TransactionFilters }
