// frontend/src/components/states/EmptyState.tsx
//
// Empty-data affordance for list pages. Icon + title + description,
// with an optional CTA button (e.g. "Add property"). The CTA is only
// rendered when `actionLabel` is provided so the component degrades
// gracefully to a plain empty-state copy block.
import { type ComponentType, type ReactNode } from 'react'
import { Inbox } from 'lucide-react'

import { Button } from '@/components/ui/button'

type Props = {
  title?: string
  description?: ReactNode
  /** Override the leading icon. Defaults to `Inbox`. */
  icon?: ComponentType<{ className?: string }>
  /** Show a CTA button. */
  actionLabel?: string
  onAction?: () => void
}

export function EmptyState({
  title = 'Nothing here yet',
  description,
  icon: Icon = Inbox,
  actionLabel,
  onAction,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="rounded-full bg-muted p-3 text-muted-foreground">
        <Icon className="size-6" />
      </div>
      <div className="space-y-1">
        <p className="font-medium">{title}</p>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actionLabel ? (
        <Button onClick={onAction}>{actionLabel}</Button>
      ) : null}
    </div>
  )
}
