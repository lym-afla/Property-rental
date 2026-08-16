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

export type ChartThemeMode = 'light' | 'dark'

const lightColors = [
  '#2563EB', '#D97706', '#059669', '#7C3AED', '#DC2626',
  '#0891B2', '#C026D3', '#65A30D', '#475569',
] as const

// Dark variants lift only the hues whose lightness falls below 3:1 on the
// dark card surface (oklch(0.205 0 0) ≈ #171717); verified pairs recorded in
// DESIGN.md. Hue order and series semantics never change between modes.
const darkColors = [
  '#3B82F6', '#D97706', '#059669', '#8B5CF6', '#EF4444',
  '#0891B2', '#C026D3', '#65A30D', '#64748B',
] as const

const lightExtendedColors = [
  '#EA580C', '#0D9488', '#E11D48', '#4F46E5', '#84CC16',
  '#A21CAF', '#0369A1', '#9F1239', '#166534', '#4338CA',
] as const

const darkExtendedColors = [
  '#EA580C', '#0D9488', '#E11D48', '#6366F1', '#84CC16',
  '#D946EF', '#0284C7', '#F43F5E', '#15803D', '#818CF8',
] as const

const seriesColors: Record<ChartThemeMode, readonly string[]> = {
  light: [...lightColors, ...lightExtendedColors],
  dark: [...darkColors, ...darkExtendedColors],
}

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

const visualTokenKeys: readonly SeriesVisualToken[] = [
  'primary', 'secondary', 'tertiary', 'quaternary', 'quinary',
  'senary', 'septenary', 'octonary', 'nonary',
]

function buildVisualTokens(mode: ChartThemeMode): Record<SeriesVisualToken, ChartSeriesStyle> {
  const palette = seriesColors[mode]
  return Object.fromEntries(
    visualTokenKeys.map((token, index) => [token, { color: palette[index], strokeWidth: 2.5 }]),
  ) as Record<SeriesVisualToken, ChartSeriesStyle>
}

const visualTokensByMode: Record<ChartThemeMode, Record<SeriesVisualToken, ChartSeriesStyle>> = {
  light: buildVisualTokens('light'),
  dark: buildVisualTokens('dark'),
}

// Light-mode table kept for callers that resolve colors outside React.
export const chartVisualTokens: Record<SeriesVisualToken, ChartSeriesStyle> = visualTokensByMode.light

export function chartSeriesStyle(token?: string, mode: ChartThemeMode = 'light'): ChartSeriesStyle {
  const tokens = visualTokensByMode[mode]
  return tokens[token as SeriesVisualToken] ?? tokens.nonary
}

export function chartSeriesColor(index: number, mode: ChartThemeMode = 'light'): string {
  const palette = seriesColors[mode]
  if (index < palette.length) return palette[index]
  const overflow = index - palette.length
  const hue = Math.round((17 + overflow * 137.508) % 360)
  const lightness = mode === 'dark'
    ? (Math.floor(overflow / 360) % 2 === 0 ? 58 : 70)
    : (Math.floor(overflow / 360) % 2 === 0 ? 46 : 58)
  return `hsl(${hue} 72% ${lightness}%)`
}

// Recharts defaults axis lines and ticks to #666, which dims on dark
// surfaces. Classes override the SVG attribute defaults and follow the
// muted-foreground token in both themes. Spread onto XAxis/YAxis.
export const CHART_AXIS_PROPS = {
  axisLine: { className: 'stroke-muted-foreground' },
  tickLine: { className: 'stroke-muted-foreground' },
  tick: { className: 'fill-muted-foreground' },
} as const
