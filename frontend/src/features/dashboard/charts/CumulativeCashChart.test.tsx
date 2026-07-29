import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CumulativeCashChart } from './CumulativeCashChart'

vi.mock('recharts', async (importOriginal) => ({ ...(await importOriginal<typeof import('recharts')>()), ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }))

const data = { metric: 'portfolio_cash_flow' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const, start: '2026-01-01', end: '2026-03-31', series: [{ key: 'net_income', label: 'Net income', kind: 'net' }, { key: 'cumulative_net_income', label: 'Cumulative net income', kind: 'cumulative' }], points: [
  { period_start: '2026-01-01', period_end: '2026-01-31', net_income: 100, cumulative_net_income: 100 },
  { period_start: '2026-02-01', period_end: '2026-02-28', net_income: -50, cumulative_net_income: 50 },
  { period_start: '2026-03-01', period_end: '2026-03-31', net_income: 200, cumulative_net_income: 250 },
] }

describe('CumulativeCashChart', () => {
  it('shows the final cumulative cash label for a sparse three-period response', async () => {
    const user = userEvent.setup()
    render(<CumulativeCashChart data={data} />)
    expect(screen.getByText('Final cumulative cash: $250')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Cumulative cash exact values' })).toHaveTextContent('$250')
  })

  it('shows an empty state when periods have no cumulative series', () => {
    render(<CumulativeCashChart data={{ ...data, series: [{ key: 'net_income', label: 'Net income', kind: 'net' }] }} />)
    expect(screen.getByText('No cumulative cash data for this selection.')).toBeInTheDocument()
  })
})
