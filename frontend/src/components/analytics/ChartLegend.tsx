import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { chartSeriesStyle, type AnalyticsSeriesDefinition } from './chartTheme'

type ChartLegendProps = {
  series: readonly AnalyticsSeriesDefinition[]
  hiddenKeys: ReadonlySet<string>
  onToggle: (key: string) => void
}

export function ChartLegend({ series, hiddenKeys, onToggle }: ChartLegendProps) {
  return (
    <div aria-label="Chart series" className="flex flex-wrap gap-2" role="group">
      {series.map((item) => {
        const visible = !hiddenKeys.has(item.key)
        const style = chartSeriesStyle(item.kind)
        return (
          <Button
            key={item.key}
            type="button"
            variant="outline"
            className="min-h-11 gap-2 px-3 focus-visible:ring-3"
            aria-label={item.label}
            aria-pressed={visible}
            onClick={() => onToggle(item.key)}
          >
            <span
              aria-hidden="true"
              className={cn('size-2.5 rounded-full border-2', !visible && 'opacity-40')}
              style={{ backgroundColor: style.color, borderColor: style.color }}
            />
            <span className={cn(!visible && 'line-through')}>{item.label}</span>
            <span aria-hidden="true" className="sr-only">{visible ? ' visible' : ' hidden'}</span>
          </Button>
        )
      })}
    </div>
  )
}
