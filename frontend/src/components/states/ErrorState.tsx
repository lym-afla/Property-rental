// frontend/src/components/states/ErrorState.tsx
//
// Error affordance for failed queries / mutations. Renders the message
// (or a sensible default) plus a Retry button that the caller wires to
// whatever recovery makes sense — usually `refetch()` from a React
// Query hook.
import { type ComponentType } from 'react'
import { TriangleAlert, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'

type Props = {
  message?: string
  /** Override the leading icon. Defaults to `TriangleAlert`. */
  icon?: ComponentType<{ className?: string }>
  onRetry?: () => void
  retryLabel?: string
}

export function ErrorState({
  message = 'Something went wrong',
  icon: Icon = TriangleAlert,
  onRetry,
  retryLabel = 'Retry',
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="rounded-full bg-destructive/10 p-3 text-destructive">
        <Icon className="size-6" />
      </div>
      <p className="text-sm text-muted-foreground">{message}</p>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry}>
          <RefreshCw className="size-4" />
          {retryLabel}
        </Button>
      ) : null}
    </div>
  )
}
