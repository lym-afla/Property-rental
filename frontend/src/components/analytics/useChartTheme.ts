import { useTheme } from 'next-themes'

import {
  chartSeriesColor,
  chartSeriesStyle,
  type ChartSeriesStyle,
  type ChartThemeMode,
} from './chartTheme'

// Resolves the chart palette for the active theme. Falls back to light when
// no ThemeProvider is mounted (unit tests) or the theme is still resolving.
export function useChartTheme() {
  const { resolvedTheme } = useTheme()
  const mode: ChartThemeMode = resolvedTheme === 'dark' ? 'dark' : 'light'
  return {
    mode,
    style: (token?: string): ChartSeriesStyle => chartSeriesStyle(token, mode),
    color: (index: number): string => chartSeriesColor(index, mode),
  }
}
