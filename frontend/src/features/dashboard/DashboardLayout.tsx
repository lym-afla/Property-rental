import { useMemo, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

import { DashboardFilters } from './DashboardFilters'
import { DashboardSectionNav } from './DashboardSectionNav'
import {
  parseDashboardFilters,
  serializeDashboardFilters,
  type DashboardFilterState,
} from './filters'

type Props = {
  defaults: DashboardFilterState
  properties: readonly { id: number; name: string }[]
  children: (filters: DashboardFilterState, onChange: (next: DashboardFilterState) => void) => ReactNode
}

const SECTION_LABELS: Record<DashboardFilterState['section'], string> = {
  overview: 'Overview',
  'income-costs': 'Income & Costs',
  portfolio: 'Portfolio',
  risk: 'Risk',
}

export function DashboardLayout({ defaults, properties, children }: Props) {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(
    () => parseDashboardFilters(searchParams, defaults),
    [searchParams, defaults],
  )

  const setFilters = (next: DashboardFilterState) => {
    setSearchParams(serializeDashboardFilters(next))
  }

  const sectionLabel = SECTION_LABELS[filters.section]

  return (
    <div className="space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">Investment dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Portfolio performance as of {filters.end} in {filters.currency}.
        </p>
      </header>
      <DashboardFilters
        filters={filters}
        properties={properties}
        onChange={setFilters}
        onReset={() => setFilters(defaults)}
      />
      <DashboardSectionNav
        section={filters.section}
        onChange={(section) => setFilters({ ...filters, section })}
      />
      <section aria-labelledby="dashboard-section-heading" className="space-y-6">
        <div>
          <h2 id="dashboard-section-heading" className="text-xl font-semibold">
            {sectionLabel} analysis
          </h2>
          <p className="text-sm text-muted-foreground">
            {filters.start} to {filters.end} · {filters.grain} · {filters.currency}
          </p>
        </div>
        {children(filters, setFilters)}
      </section>
    </div>
  )
}
