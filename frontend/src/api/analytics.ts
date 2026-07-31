import { useQuery } from '@tanstack/react-query'

import {
  expenseDriversSchema,
  portfolioCashFlowSchema,
  portfolioOccupancySchema,
  profitLossSchema,
  portfolioSummarySchema,
  propertyBreakdownSchema,
  propertyContributionSchema,
  propertyValuationSchema,
  propertyYieldsSchema,
  tenantRentPerformanceSchema,
  type PropertyBreakdownParams,
  type PortfolioAnalyticsParams,
  type ProfitLossParams,
  type TenantRentPerformanceParams,
} from '@/types/analytics'
import { apiFetch } from './client'
import { normalizePropertyIds, queryKeys } from './keys'

function analyticsUrl(
  path: string,
  params: PortfolioAnalyticsParams,
  extras: Record<string, string | undefined> = {},
): string {
  const search = new URLSearchParams()
  if (params.start !== undefined) search.set('start', params.start)
  if (params.end !== undefined) search.set('end', params.end)
  if (params.currency !== undefined) search.set('currency', params.currency)
  if (params.grain !== undefined) search.set('grain', params.grain)
  for (const propertyId of normalizePropertyIds(params.propertyIds)) {
    search.append('property', String(propertyId))
  }
  for (const [key, value] of Object.entries(extras)) {
    if (value !== undefined) search.set(key, value)
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

async function fetchValidated<T>(
  path: string,
  schema: { parse(value: unknown): T },
): Promise<T> {
  const payload = await apiFetch<unknown>(path)
  return schema.parse(payload)
}

export function usePortfolioSummary(params: PortfolioAnalyticsParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.summary(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/summary/', params),
        portfolioSummarySchema,
      ),
  })
}

export function usePortfolioCashFlow(params: PortfolioAnalyticsParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.cashFlow(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/cash-flow/', params),
        portfolioCashFlowSchema,
      ),
  })
}

export function useExpenseDrivers(params: PortfolioAnalyticsParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.expenseDrivers(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/expenses/', params),
        expenseDriversSchema,
      ),
  })
}

export function useProfitLoss(params: ProfitLossParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.profitLoss(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/profit-loss/', params),
        profitLossSchema,
      ),
    enabled: Boolean(params.end && params.currency),
  })
}

export function usePropertyContribution(params: PortfolioAnalyticsParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.propertyContribution(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/property-contribution/', params),
        propertyContributionSchema,
      ),
  })
}

export function usePropertyYields(params: PortfolioAnalyticsParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.propertyYields(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/yields/', params),
        propertyYieldsSchema,
      ),
  })
}

export function usePropertyBreakdown(params: PropertyBreakdownParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.propertyBreakdown(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/property-breakdown/', params, {
          measure: params.measure,
        }),
        propertyBreakdownSchema,
      ),
  })
}

export function usePortfolioOccupancy(params: PortfolioAnalyticsParams) {
  return useQuery({
    queryKey: queryKeys.analytics.portfolio.occupancy(params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl('/analytics/portfolio/occupancy/', params),
        portfolioOccupancySchema,
      ),
  })
}

export function usePropertyValuationAnalytics(
  propertyId: number,
  params: { start?: string; end?: string } = {},
) {
  const search = new URLSearchParams()
  if (params.start !== undefined) search.set('start', params.start)
  if (params.end !== undefined) search.set('end', params.end)
  const query = search.toString()
  const path = `/analytics/properties/${propertyId}/valuation/${query ? `?${query}` : ''}`

  return useQuery({
    queryKey: queryKeys.analytics.propertyValuation(propertyId, params),
    queryFn: () => fetchValidated(path, propertyValuationSchema),
    enabled: propertyId > 0,
  })
}

export function useTenantRentPerformance(
  tenantId: number,
  params: TenantRentPerformanceParams,
) {
  const { start, end, grain } = params
  return useQuery({
    queryKey: queryKeys.analytics.tenantRentPerformance(tenantId, params),
    queryFn: () =>
      fetchValidated(
        analyticsUrl(
          `/analytics/tenants/${tenantId}/rent-performance/`,
          { start, end, grain },
        ),
        tenantRentPerformanceSchema,
      ),
    enabled: tenantId > 0,
  })
}
