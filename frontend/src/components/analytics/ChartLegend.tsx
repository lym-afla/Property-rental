import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { type AnalyticsSeriesDefinition, type ChartSeriesStyle } from './chartTheme'
import { useChartTheme } from './useChartTheme'

type ChartLegendProps = {
  series: readonly AnalyticsSeriesDefinition[]
  hiddenKeys: ReadonlySet<string>
  onToggle: (key: string) => void
  resolveStyle?: (series: AnalyticsSeriesDefinition) => ChartSeriesStyle
}

export function ChartLegend({ series, hiddenKeys, onToggle, resolveStyle }: ChartLegendProps) {
  const charts = useChartTheme()
  return (
    <div aria-label="Chart series" className="flex flex-wrap gap-2" role="group">
      {series.map((item) => {
        const visible = !hiddenKeys.has(item.key)
        const style = resolveStyle?.(item) ?? charts.style(item.visualToken)
        return (
          <Button
            key={item.key}
            type="button"
            variant="outline"
            className="min-h-11 gap-2 px-3"
            aria-label={item.label}
            aria-pressed={visible}
            onClick={() => onToggle(item.key)}
          >
            <span
              aria-hidden="true"
              data-testid={`legend-marker-${item.key}`}
              data-marker="swatch"
              className={cn('size-2.5 shrink-0 rounded-none border-2', !visible && 'opacity-40')}
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
