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

const extendedColors = [
  '#EA580C', '#0D9488', '#E11D48', '#4F46E5', '#84CC16',
  '#A21CAF', '#0369A1', '#9F1239', '#166534', '#4338CA',
] as const

const propertySeriesColors = [...colors, ...extendedColors]

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

export function chartSeriesColor(index: number): string {
  if (index < propertySeriesColors.length) return propertySeriesColors[index]
  const hue = Math.round((17 + (index - propertySeriesColors.length) * 137.508) % 360)
  const lightness = Math.floor((index - propertySeriesColors.length) / 360) % 2 === 0 ? 46 : 58
  return `hsl(${hue} 72% ${lightness}%)`
}
