import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RevenueExpenseTrendChart } from './RevenueExpenseTrendChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: ({ name, strokeDasharray }: { name: string; strokeDasharray?: string }) => <span data-testid={`trend-${name}`} data-dash={strokeDasharray ?? 'solid'} />,
}))

const data = { metric: 'portfolio_cash_flow' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const, start: '2026-01-01', end: '2026-03-31', series: [{ key: 'total_income', label: 'Total income', kind: 'income_total' }, { key: 'total_expenses', label: 'Total expenses', kind: 'expense_total' }], points: [
  { period_start: '2026-01-01', period_end: '2026-01-31', total_income: 1000, total_expenses: -250 },
  { period_start: '2026-02-01', period_end: '2026-02-28', total_income: 900, total_expenses: -300 },
  { period_start: '2026-03-01', period_end: '2026-03-31', total_income: 1200, total_expenses: -150 },
] }

describe('RevenueExpenseTrendChart', () => {
  it('hides a selected server series without relying on its color', async () => {
    const user = userEvent.setup()
    render(<RevenueExpenseTrendChart data={data} />)
    const expenses = screen.getByRole('button', { name: 'Total expenses' })
    await user.click(expenses)
    expect(expenses).toHaveAttribute('aria-pressed', 'false')
    expect(expenses).toHaveTextContent('Total expenses')
  })

  it('applies distinct dash identities to the plotted income and expense traces', () => {
    render(<RevenueExpenseTrendChart data={data} />)
    expect(screen.getByTestId('trend-Total income').getAttribute('data-dash')).not.toBe(
      screen.getByTestId('trend-Total expenses').getAttribute('data-dash'),
    )
  })

  it('shows an empty state when periods have no income or expense series', () => {
    render(<RevenueExpenseTrendChart data={{ ...data, series: [{ key: 'net_income', label: 'Net income', kind: 'net' }] }} />)
    expect(screen.getByText('No revenue and expenses data for this selection.')).toBeInTheDocument()
  })
})
