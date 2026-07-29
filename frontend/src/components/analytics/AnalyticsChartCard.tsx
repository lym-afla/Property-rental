import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

import { AnalyticsTable, type AnalyticsTableColumn, type AnalyticsTableRow } from './AnalyticsTable'

export type AnalyticsChartState =
  | { status: 'loading' }
  | { status: 'error'; message?: string; onRetry?: () => void }
  | { status: 'empty'; message: string; action?: ReactNode }
  | { status: 'success' }

export type AnalyticsChartTable = {
  columns: readonly AnalyticsTableColumn[]
  rows: readonly AnalyticsTableRow[]
}

type AnalyticsChartCardProps = {
  state: AnalyticsChartState
  title: string
  subtitle?: ReactNode
  controls?: ReactNode
  summary?: ReactNode
  table?: AnalyticsChartTable
  children?: ReactNode
}

export function AnalyticsChartCard({
  state,
  title,
  subtitle,
  controls,
  summary,
  table,
  children,
}: AnalyticsChartCardProps) {
  const [showTable, setShowTable] = useState(false)
  const canShowTable = state.status === 'success' && table !== undefined

  return (
    <Card>
      <CardHeader className="gap-3 sm:flex sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
          {summary && <div className="mt-2">{summary}</div>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {controls}
          {canShowTable && (
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              aria-pressed={showTable}
              onClick={() => setShowTable((current) => !current)}
            >
              {showTable ? 'Chart' : 'Table'}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {state.status === 'loading' && (
          <Skeleton
            data-testid="analytics-chart-skeleton"
            aria-label={`${title} loading`}
            className="h-[300px] w-full motion-reduce:animate-none"
          />
        )}
        {state.status === 'error' && (
          <div className="flex h-[300px] flex-col items-center justify-center gap-3 text-center">
            <p role="alert">{state.message ?? `Could not load ${title}.`}</p>
            {state.onRetry && <Button className="min-h-11" onClick={state.onRetry}>Retry</Button>}
          </div>
        )}
        {state.status === 'empty' && (
          <div className="flex h-[300px] flex-col items-center justify-center gap-3 text-center">
            <p>{state.message}</p>
            {state.action}
          </div>
        )}
        {state.status === 'success' && (showTable && table ? (
          <AnalyticsTable label={`${title} exact values`} {...table} />
        ) : (
          <div className="h-[300px] w-full">{children}</div>
        ))}
      </CardContent>
    </Card>
  )
}
