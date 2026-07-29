import { Button } from '@/components/ui/button'
import type { DashboardSection } from './filters'

const DASHBOARD_SECTION_LABELS: Record<DashboardSection, string> = {
  overview: 'Overview',
  'income-costs': 'Income & Costs',
  portfolio: 'Portfolio',
  risk: 'Risk',
}

type Props = {
  section: DashboardSection
  onChange: (section: DashboardSection) => void
}

export function DashboardSectionNav({ section, onChange }: Props) {
  return (
    <nav aria-label="Dashboard sections" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {(Object.entries(DASHBOARD_SECTION_LABELS) as [DashboardSection, string][]).map(([value, label]) => (
        <Button
          key={value}
          type="button"
          variant={section === value ? 'default' : 'outline'}
          className="min-h-11 w-full whitespace-normal"
          aria-current={section === value ? 'page' : undefined}
          onClick={() => onChange(value)}
        >
          {label}
        </Button>
      ))}
    </nav>
  )
}
