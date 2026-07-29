export type AnalyticsSeriesDefinition = {
  key: string
  label: string
  kind: string
  visualToken?: SeriesVisualToken
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
} as const

export type SeriesVisualToken = 'primary' | 'secondary' | 'tertiary' | 'default'

export const chartVisualTokens: Record<SeriesVisualToken, ChartSeriesStyle> = {
  primary: { color: palette.blue, strokeWidth: 2.5, marker: 'circle' },
  secondary: { color: palette.gold, strokeWidth: 2.5, marker: 'square' },
  tertiary: { color: palette.slate, strokeWidth: 2.5, marker: 'diamond' },
  default: { color: palette.slate, strokeWidth: 2.5, marker: 'circle' },
}

export function chartSeriesStyle(token?: string): ChartSeriesStyle {
  return chartVisualTokens[token as SeriesVisualToken] ?? chartVisualTokens.default
}
