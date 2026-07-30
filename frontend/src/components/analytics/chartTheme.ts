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
  strokeDasharray?: string
}

const palette = {
  blue: '#2563eb',
  gold: '#b7791f',
  slate: '#475569',
} as const

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
  | 'default'

export const chartVisualTokens: Record<SeriesVisualToken, ChartSeriesStyle> = {
  primary: { color: palette.blue, strokeWidth: 2.5, marker: 'circle' },
  secondary: { color: palette.gold, strokeWidth: 2.5, marker: 'square', strokeDasharray: '8 4' },
  tertiary: { color: palette.slate, strokeWidth: 2.5, marker: 'diamond', strokeDasharray: '2 3' },
  quaternary: { color: palette.blue, strokeWidth: 2.5, marker: 'square', strokeDasharray: '10 3 2 3' },
  quinary: { color: palette.gold, strokeWidth: 2.5, marker: 'diamond', strokeDasharray: '4 3' },
  senary: { color: palette.slate, strokeWidth: 2.5, marker: 'circle', strokeDasharray: '1 3' },
  septenary: { color: palette.blue, strokeWidth: 2.5, marker: 'diamond', strokeDasharray: '12 3' },
  octonary: { color: palette.gold, strokeWidth: 2.5, marker: 'circle', strokeDasharray: '6 2 1 2' },
  nonary: { color: palette.slate, strokeWidth: 2.5, marker: 'square', strokeDasharray: '3 2 1 2' },
  default: { color: palette.slate, strokeWidth: 2.5, marker: 'circle', strokeDasharray: '10 3 2 3' },
}

export function chartSeriesStyle(token?: string): ChartSeriesStyle {
  return chartVisualTokens[token as SeriesVisualToken] ?? chartVisualTokens.default
}

export function chartPatternFill(prefix: string, token?: string): string {
  return `url(#${prefix}-${token ?? 'default'})`
}
