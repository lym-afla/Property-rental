// frontend/src/components/dashboard/KpiCard.tsx
//
// Reusable KPI card (Plan C Task 10). Renders a labelled value inside a
// shadcn Card with a small optional helper line. Designed to drop into the
// HomePage dashboard's KPI row but generic enough for any summary tile.
//
// The `value` is a ReactNode rather than a string so callers can pass a
// `<Skeleton>` while their data is loading (mirrors the pattern already used
// by the placeholder HomePage and the property/tenant detail headers).
import type { ReactNode } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type Props = {
  label: string
  value: ReactNode
  description?: string
  className?: string
}

export function KpiCard({ label, value, description, className }: Props) {
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <div className="text-2xl font-bold">{value}</div>
        {description ? (
          <p className="text-xs text-muted-foreground">{description}</p>
        ) : null}
      </CardContent>
    </Card>
  )
}
