export type AnalyticsSeriesDefinition = {
  key: string
  label: string
  kind: string
}

export type ChartSeriesStyle = {
  color: string
  strokeWidth: number
  marker: 'circle' | 'square' | 'diamond'
}

const palette = {
  blue: '#2563eb',
  gold: '#b7791f',
  slate: '#475569',
  green: '#15803d',
  red: '#b91c1c',
} as const

export const chartCategoryStyles: Record<string, ChartSeriesStyle> = {
  income: { color: palette.blue, strokeWidth: 2.5, marker: 'circle' },
  revenue: { color: palette.blue, strokeWidth: 2.5, marker: 'circle' },
  expected: { color: palette.blue, strokeWidth: 2.5, marker: 'circle' },
  total: { color: palette.blue, strokeWidth: 2.5, marker: 'circle' },
  costs: { color: palette.gold, strokeWidth: 2.5, marker: 'square' },
  debt: { color: palette.gold, strokeWidth: 2.5, marker: 'square' },
  variance: { color: palette.red, strokeWidth: 2.5, marker: 'diamond' },
  equity: { color: palette.green, strokeWidth: 2.5, marker: 'diamond' },
  received: { color: palette.green, strokeWidth: 2.5, marker: 'diamond' },
  cumulative: { color: palette.slate, strokeWidth: 2.5, marker: 'square' },
  default: { color: palette.slate, strokeWidth: 2.5, marker: 'circle' },
}

export function chartSeriesStyle(kind: string): ChartSeriesStyle {
  return chartCategoryStyles[kind] ?? chartCategoryStyles.default
}
