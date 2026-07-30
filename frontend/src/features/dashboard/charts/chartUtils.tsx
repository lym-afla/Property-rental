import type { ReactNode } from 'react'

import type { AnalyticsChartState, AnalyticsChartTable } from '@/components/analytics/AnalyticsChartCard'
import type { AnalyticsSeriesDefinition } from '@/components/analytics/chartTheme'
import { formatCurrency, formatDate } from '@/lib/format'
export type PortfolioChartData = {
  currency?: string
  series: Array<{ key: string; label: string; kind: string }>
  points: Array<{ period_start: string; period_end: string; [key: string]: string | number | null }>
}

export type ChartDataProps = {
  data?: PortfolioChartData
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

export type DrillDown = {
  from: string
  to: string
  category: string
  currency: string
  propertyIds: readonly number[]
}

export function chartState(
  title: string,
  { data, isLoading, isError, onRetry }: ChartDataProps,
  hasDisplayableData = data !== undefined && data.points.length > 0,
): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: `Could not load ${title}.`, onRetry }
  if (!data || !hasDisplayableData) return { status: 'empty', message: `No ${title.toLowerCase()} data for this selection.` }
  return { status: 'success' }
}

export function hasSeriesValues(
  data: PortfolioChartData | undefined,
  series: readonly { key: string }[],
): boolean {
  return data !== undefined && series.length > 0 && data.points.some((point) =>
    series.some((item) => typeof point[item.key] === 'number'),
  )
}

export function seriesWithVisualTokens(
  series: readonly { key: string; label: string; kind: string }[],
): AnalyticsSeriesDefinition[] {
  const tokens = [
    'primary',
    'secondary',
    'tertiary',
    'quaternary',
    'quinary',
    'senary',
    'septenary',
    'octonary',
    'nonary',
  ] as const
  return series.map((item, index) => ({ ...item, visualToken: tokens[index % tokens.length] }))
}

export function cashTable(
  data: PortfolioChartData,
  series: readonly { key: string; label: string }[],
): AnalyticsChartTable {
  return {
    columns: [
      { key: 'period', label: 'Period' },
      ...series.map((item) => ({ key: item.key, label: item.label, numeric: true })),
    ],
    rows: data.points.map((point) => {
      const row: Record<string, ReactNode> = { period: formatDate(point.period_start) }
      for (const item of series) {
        row[item.key] = formatCurrency(point[item.key] as number | null, data.currency ?? '')
      }
      return row
    }),
  }
}

export function compactPeriod(value: string): string {
  return formatDate(value)
}
