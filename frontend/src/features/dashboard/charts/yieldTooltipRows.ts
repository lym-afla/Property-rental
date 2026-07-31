import type { TooltipPayloadEntry } from 'recharts'

import type { ChartTooltipRow } from '@/components/analytics/ChartTooltip'

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function formatYield(value: number) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`
}

export function yieldTooltipRows(payload: readonly TooltipPayloadEntry[]): ChartTooltipRow[] {
  return payload.flatMap((item) => (
    item.dataKey === 'yield' && isFiniteNumber(item.value)
      ? [{ label: String(item.name), value: formatYield(item.value) }]
      : []
  ))
}
