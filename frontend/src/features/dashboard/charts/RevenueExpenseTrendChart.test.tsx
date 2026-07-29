import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RevenueExpenseTrendChart } from './RevenueExpenseTrendChart'

vi.mock('recharts', async (importOriginal) => ({ ...(await importOriginal<typeof import('recharts')>()), ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }))

const data = { metric: 'portfolio_cash_flow' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const, start: '2026-01-01', end: '2026-03-31', series: [{ key: 'total_income', label: 'Total income', kind: 'income' }, { key: 'total_expenses', label: 'Total expenses', kind: 'expense' }], points: [
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
})
