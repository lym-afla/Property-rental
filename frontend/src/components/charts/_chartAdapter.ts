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
  // The tenant chart-data endpoint returns a single dataset WITHOUT a
  // `label` field (see `services/charts.py::get_chart_data` tenant
  // branch). Rather than let every caller special-case this, we default
  // a lone unlabeled dataset to "Rent" — the only single-series chart
  // in the app is the tenant rent history, so the label is unambiguous.
  const labeledDatasets =
    datasets.length === 1 && !datasets[0].label
      ? [{ ...datasets[0], label: 'Rent' }]
      : datasets
  // Build flat objects: [{ label: 'Jan-24', rent: 1000, utilities: 200 }, ...]
  const chartData = labels.map((label, i) => {
    const row: Record<string, number | string> = { label }
    labeledDatasets.forEach((ds, j) => {
      const key = ds.label || `series_${j}`
      row[key] = ds.data[i] ?? 0
    })
    return row
  })
  // Build series metadata
  const series = labeledDatasets.map((ds, j) => ({
    key: ds.label || `series_${j}`,
    label: ds.label || `Series ${j + 1}`,
    color: colorForCategory(ds.label || '', j),
  }))
  return { chartData, series, currency }
}
