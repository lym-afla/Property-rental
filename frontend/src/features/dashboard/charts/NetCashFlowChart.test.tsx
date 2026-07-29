import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { NetCashFlowChart } from './NetCashFlowChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children, stackOffset }: { children: React.ReactNode; stackOffset?: string }) => <div data-testid="cash-flow-plot" data-stack-offset={stackOffset}>{children}</div>,
  Bar: ({ name, fill }: { name: string; fill: string }) => <span data-testid={`cash-bar-${name}`} data-fill={fill} />,
}))

const data = {
  metric: 'portfolio_cash_flow' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const,
  start: '2026-01-01', end: '2026-12-31',
  series: [
    { key: 'rent', label: 'Rent', kind: 'income_category' },
    { key: 'utilities', label: 'Utilities', kind: 'expense_category' },
    { key: 'total_income', label: 'Total income', kind: 'income_total' },
    { key: 'total_expenses', label: 'Total expenses', kind: 'expense_total' },
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
    expect(screen.getByTestId('cash-flow-plot')).toHaveAttribute('data-stack-offset', 'sign')
    expect(screen.getByTestId('cash-bar-Rent').getAttribute('data-fill')).toMatch(/^url\(#/)
    expect(screen.getByTestId('cash-bar-Rent').getAttribute('data-fill')).not.toBe(screen.getByTestId('cash-bar-Utilities').getAttribute('data-fill'))
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Net cash flow exact values' })).toHaveTextContent('$1,000')
    expect(screen.getByRole('table', { name: 'Net cash flow exact values' })).toHaveTextContent('$-250')
  })

  it('uses a visible drill-down disclosure for pointer and keyboard activation', async () => {
    const user = userEvent.setup()
    const onDrillDown = vi.fn()
    render(<NetCashFlowChart data={data} propertyIds={[3, 1]} onDrillDown={onDrillDown} />)

    const disclosure = screen.getByText('Drill down to transactions')
    expect(disclosure).not.toHaveClass('sr-only')
    await user.click(disclosure)
    const drillDown = screen.getByRole('button', { name: 'View Rent transactions for 1 Jan 2026' })
    await user.click(drillDown)
    drillDown.focus()
    await user.keyboard('{Enter}')
    expect(onDrillDown).toHaveBeenCalledTimes(2)
    expect(onDrillDown).toHaveBeenCalledWith({
      from: '2026-01-01', to: '2026-01-28', category: 'rent', currency: 'USD', propertyIds: [3, 1],
    })
  })

  it('shows an empty state when a response has periods but no income or expense series', () => {
    render(<NetCashFlowChart data={{ ...data, series: [{ key: 'net_income', label: 'Net income', kind: 'net' }], points: [{ period_start: '2026-01-01', period_end: '2026-01-31', net_income: 750 }] }} />)
    expect(screen.getByText('No net cash flow data for this selection.')).toBeInTheDocument()
  })
})
