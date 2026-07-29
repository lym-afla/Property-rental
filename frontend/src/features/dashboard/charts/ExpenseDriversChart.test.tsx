import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ExpenseDriversChart } from './ExpenseDriversChart'

vi.mock('recharts', async (importOriginal) => ({ ...(await importOriginal<typeof import('recharts')>()), ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }))

const data = { metric: 'expense_drivers' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const, start: '2026-01-01', end: '2026-03-31', series: [{ key: 'major_repairs', label: 'Major repairs and long-running maintenance', kind: 'expense' }, { key: 'utilities', label: 'Utilities', kind: 'expense' }], points: [
  { period_start: '2026-01-01', period_end: '2026-01-31', major_repairs: -1000, utilities: -100 },
  { period_start: '2026-02-01', period_end: '2026-02-28', major_repairs: -500, utilities: -250 },
  { period_start: '2026-03-01', period_end: '2026-03-31', major_repairs: -500, utilities: -200 },
] }

describe('ExpenseDriversChart', () => {
  it('ranks backend expense categories with their long labels and exposes exact totals', async () => {
    const user = userEvent.setup()
    render(<ExpenseDriversChart data={data} />)
    expect(screen.getByTestId('expense-driver-major_repairs')).toHaveTextContent('Major repairs and long-running maintenance')
    expect(screen.getByTestId('expense-driver-major_repairs')).toHaveAttribute('data-rank', '1')
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Expense drivers exact values' })).toHaveTextContent('$2,000')
  })

  it('shows an empty state when expense rows total zero across populated periods', () => {
    render(<ExpenseDriversChart data={{ ...data, points: data.points.map((point) => ({ ...point, major_repairs: 0, utilities: 0 })) }} />)
    expect(screen.getByText('No expense drivers data for this selection.')).toBeInTheDocument()
  })
})
