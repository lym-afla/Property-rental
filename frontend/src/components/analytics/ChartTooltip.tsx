import type { ReactNode } from 'react'

export type ChartTooltipRow = {
  label: string
  value: ReactNode
}

type ChartTooltipProps = {
  label: string
  rows: readonly ChartTooltipRow[]
}

export function ChartTooltip({ label, rows }: ChartTooltipProps) {
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <p className="font-medium">{label}</p>
      <dl className="mt-1 grid grid-cols-[auto_auto] gap-x-4 gap-y-1 tabular-nums">
        {rows.map((row, index) => (
          <div key={`${row.label}-${index}`} className="contents">
            <dt className="text-muted-foreground">{row.label}</dt>
            <dd className="text-right font-medium">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
