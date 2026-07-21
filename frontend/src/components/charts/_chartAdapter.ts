import type { ChartDataResponse } from '@/api/charts'
import { colorForCategory } from './_chartTheme'

export type TransformedChartData = {
  chartData: Record<string, number | string>[]
  series: { key: string; label: string; color: string }[]
  currency: string
}

// Map currency symbols to codes for consistent formatting
const SYMBOL_TO_CODE: Record<string, string> = { '$': 'USD', '€': 'EUR', '£': 'GBP', '₽': 'RUB' }

function normalizeCurrency(currency: string): string {
  return SYMBOL_TO_CODE[currency] ?? currency
}

export function transformForRecharts(data: ChartDataResponse): TransformedChartData {
  const { labels, datasets, currency: rawCurrency } = data
  const currency = normalizeCurrency(rawCurrency)
  // Build flat objects: [{ label: 'Jan-24', rent: 1000, utilities: 200 }, ...]
  const chartData = labels.map((label, i) => {
    const row: Record<string, number | string> = { label }
    datasets.forEach((ds, j) => {
      const key = ds.label || `series_${j}`
      row[key] = ds.data[i] ?? 0
    })
    return row
  })
  // Build series metadata
  const series = datasets.map((ds, j) => ({
    key: ds.label || `series_${j}`,
    label: ds.label || `Series ${j + 1}`,
    color: colorForCategory(ds.label || '', j),
  }))
  return { chartData, series, currency }
}
