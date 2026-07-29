import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { NetCashFlowChart } from './NetCashFlowChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const data = {
  metric: 'portfolio_cash_flow' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const,
  start: '2026-01-01', end: '2026-12-31',
  series: [
    { key: 'rent', label: 'Rent', kind: 'income' },
    { key: 'utilities', label: 'Utilities', kind: 'expense' },
    { key: 'total_income', label: 'Total income', kind: 'income' },
    { key: 'total_expenses', label: 'Total expenses', kind: 'expense' },
    { key: 'net_income', label: 'Net income', kind: 'net' },
    { key: 'cumulative_net_income', label: 'Cumulative net income', kind: 'cumulative' },
  ],
  points: Array.from({ length: 12 }, (_, index) => ({
    period_start: `2026-${String(index + 1).padStart(2, '0')}-01`,
    period_end: `2026-${String(index + 1).padStart(2, '0')}-28`,
    rent: 1000, utilities: -250, total_income: 1000, total_expenses: -250,
    net_income: 750, cumulative_net_income: (index + 1) * 750,
  })),
}

describe('NetCashFlowChart', () => {
  it('keeps signed category values and exposes a zero baseline and exact-value table', async () => {
    const user = userEvent.setup()
    render(<NetCashFlowChart data={data} />)

    expect(screen.getByLabelText('Net cash flow zero baseline')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Net cash flow exact values' })).toHaveTextContent('$1,000')
    expect(screen.getByRole('table', { name: 'Net cash flow exact values' })).toHaveTextContent('$-250')
  })

  it('drills into the server-provided period by pointer and keyboard activation', async () => {
    const user = userEvent.setup()
    const onDrillDown = vi.fn()
    render(<NetCashFlowChart data={data} propertyIds={[3, 1]} onDrillDown={onDrillDown} />)

    const drillDown = screen.getByRole('button', { name: 'View Rent transactions for 1 Jan 2026' })
    await user.click(drillDown)
    drillDown.focus()
    await user.keyboard('{Enter}')
    expect(onDrillDown).toHaveBeenCalledTimes(2)
    expect(onDrillDown).toHaveBeenCalledWith({
      from: '2026-01-01', to: '2026-01-28', category: 'rent', currency: 'USD', propertyIds: [3, 1],
    })
  })
})
