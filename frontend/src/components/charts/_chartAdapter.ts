import type { ChartDataResponse } from '@/api/charts'
import { colorForCategory } from './_chartTheme'

export type TransformedChartData = {
  chartData: Record<string, number | string>[]
  series: { key: string; label: string; color: string }[]
  currency: string
}

export function transformForRecharts(data: ChartDataResponse): TransformedChartData {
  const { labels, datasets, currency } = data
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
