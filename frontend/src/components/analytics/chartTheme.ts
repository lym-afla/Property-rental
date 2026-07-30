export type AnalyticsSeriesDefinition = {
  key: string
  label: string
  kind: string
  visualToken?: SeriesVisualToken
}

export type ChartSeriesStyle = {
  color: string
  strokeWidth: number
}

const colors = [
  '#2563EB', '#D97706', '#059669', '#7C3AED', '#DC2626',
  '#0891B2', '#C026D3', '#65A30D', '#475569',
] as const

export type SeriesVisualToken =
  | 'primary'
  | 'secondary'
  | 'tertiary'
  | 'quaternary'
  | 'quinary'
  | 'senary'
  | 'septenary'
  | 'octonary'
  | 'nonary'

export const chartVisualTokens: Record<SeriesVisualToken, ChartSeriesStyle> = {
  primary: { color: colors[0], strokeWidth: 2.5 },
  secondary: { color: colors[1], strokeWidth: 2.5 },
  tertiary: { color: colors[2], strokeWidth: 2.5 },
  quaternary: { color: colors[3], strokeWidth: 2.5 },
  quinary: { color: colors[4], strokeWidth: 2.5 },
  senary: { color: colors[5], strokeWidth: 2.5 },
  septenary: { color: colors[6], strokeWidth: 2.5 },
  octonary: { color: colors[7], strokeWidth: 2.5 },
  nonary: { color: colors[8], strokeWidth: 2.5 },
}

export function chartSeriesStyle(token?: string): ChartSeriesStyle {
  return chartVisualTokens[token as SeriesVisualToken] ?? chartVisualTokens.nonary
}
