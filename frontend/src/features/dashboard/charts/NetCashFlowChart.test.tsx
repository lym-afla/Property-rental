import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { NetCashFlowChart } from './NetCashFlowChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children, stackOffset }: { children: React.ReactNode; stackOffset?: string }) => <div data-testid="cash-flow-plot" data-stack-offset={stackOffset}>{children}</div>,
  Bar: ({ name, fill, stackId }: { name: string; fill: string; stackId?: string }) => <span data-testid="cash-bar" aria-label={name} data-fill={fill} data-stack-id={stackId} />,
  Tooltip: ({ content }: { content: (props: { active: boolean; label: string; payload: Array<{ name: string; value: unknown }> }) => React.ReactNode }) => content({ active: true, label: '2026-01-01', payload: [{ name: 'Missing', value: null }, { name: 'Invalid', value: Number.NaN }] }),
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

const depositData = {
  ...data,
  series: [
    ...data.series,
    { key: 'deposits', label: 'Security deposits', kind: 'deposit_movement' },
    { key: 'net_cash_flow', label: 'Net cash flow', kind: 'net_cash' },
  ],
  points: data.points.map((point, index) => ({ ...point, deposits: index === 0 ? 500 : -200, net_cash_flow: point.net_income + (index === 0 ? 500 : -200) })),
}

describe('NetCashFlowChart', () => {
  it('keeps signed category values and exposes a zero baseline and exact-value table', async () => {
    const user = userEvent.setup()
    render(<NetCashFlowChart data={data} />)

    expect(screen.getByLabelText('Net cash flow zero baseline')).toBeInTheDocument()
    expect(screen.getByTestId('cash-flow-plot')).toHaveAttribute('data-stack-offset', 'sign')
    expect(screen.getByRole('generic', { name: 'Rent' }).getAttribute('data-fill')).not.toMatch(/^url\(/)
    expect(screen.getByRole('generic', { name: 'Rent' }).getAttribute('data-fill')).not.toBe(screen.getByRole('generic', { name: 'Utilities' }).getAttribute('data-fill'))
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Net cash flow exact values' })).toHaveTextContent('$1,000')
    expect(screen.getByRole('table', { name: 'Net cash flow exact values' })).toHaveTextContent('($250)')
  })

  it('gives every supported cash-flow category a distinct visible mark identity', () => {
    const categories = [
      { key: 'rent', label: 'Rent', kind: 'income_category' },
      { key: 'tax', label: 'Tax', kind: 'expense_category' },
      { key: 'capex', label: 'Capex', kind: 'expense_category' },
      { key: 'management', label: 'Management', kind: 'expense_category' },
      { key: 'electricity', label: 'Electricity', kind: 'expense_category' },
      { key: 'utilities', label: 'Utilities', kind: 'expense_category' },
      { key: 'internet', label: 'Internet', kind: 'expense_category' },
      { key: 'cost_reimbursement', label: 'Cost reimbursement', kind: 'expense_category' },
      { key: 'other_expenses', label: 'Other expenses', kind: 'expense_category' },
    ]
    const categoryPoint = Object.fromEntries(categories.map(({ key }, index) => [key, index === 0 ? 1000 : -(index * 10)]))

    render(<NetCashFlowChart data={{
      ...data,
      series: [...categories, ...data.series.slice(2)],
      points: [{ ...data.points[0], ...categoryPoint }],
    }} />)

    const fills = screen.getAllByTestId('cash-bar').map((bar) => bar.getAttribute('data-fill'))
    expect(fills).toHaveLength(categories.length)
    expect(new Set(fills).size).toBe(categories.length)
  })

  it('uses a visible drill-down disclosure for pointer and keyboard activation', async () => {
    const user = userEvent.setup()
    const onDrillDown = vi.fn()
    render(<NetCashFlowChart data={data} propertyIds={[3, 1]} onDrillDown={onDrillDown} />)

    const disclosure = screen.getByText('Drill down to transactions')
    expect(disclosure).not.toHaveClass('sr-only')
    await user.click(disclosure)
    const drillDown = screen.getByRole('button', { name: 'View Rent transactions for Jan 1, 2026' })
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

  it('renders missing and invalid tooltip values as em dashes', () => {
    render(<NetCashFlowChart data={data} />)

    expect(screen.getAllByText('—')).toHaveLength(2)
  })

  describe('with security deposit series', () => {
    const renderDeposits = (onDrillDown = vi.fn()) => {
      render(<MemoryRouter><NetCashFlowChart data={depositData} onDrillDown={onDrillDown} /></MemoryRouter>)
      return onDrillDown
    }

    it('lists Security deposits in the legend with a token distinct from every category', () => {
      renderDeposits()
      expect(screen.getByRole('button', { name: /Security deposits/ })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /^Net cash flow$/ })).not.toBeInTheDocument()
      const fills = screen.getAllByTestId('cash-bar').map((bar) => bar.getAttribute('data-fill'))
      expect(fills).toHaveLength(3)
      expect(new Set(fills).size).toBe(3)
    })

    it('keeps the stack signed and draws deposits outside the category stack', () => {
      renderDeposits()
      expect(screen.getByTestId('cash-flow-plot')).toHaveAttribute('data-stack-offset', 'sign')
      expect(screen.getByRole('generic', { name: 'Security deposits' })).toHaveAttribute('data-stack-id', 'deposits')
      expect(screen.getByRole('generic', { name: 'Rent' })).toHaveAttribute('data-stack-id', 'cash-flow')
    })

    it('adds deposits and Net cash flow columns to the exact-value table', async () => {
      const user = userEvent.setup()
      renderDeposits()
      await user.click(screen.getByRole('button', { name: 'Table' }))
      const table = screen.getByRole('table', { name: 'Net cash flow exact values' })
      expect(within(table).getByRole('columnheader', { name: 'Security deposits' })).toBeInTheDocument()
      expect(within(table).getByRole('columnheader', { name: 'Net cash flow' })).toBeInTheDocument()
      expect(table).toHaveTextContent('($200)')
      expect(table).toHaveTextContent('$1,250')
    })

    it('links deposit drill-down to tenants without calling onDrillDown', async () => {
      const user = userEvent.setup()
      const onDrillDown = renderDeposits()
      await user.click(screen.getByText('Drill down to transactions'))
      const link = screen.getByRole('link', { name: 'View deposit movements for Jan 1, 2026' })
      expect(link).toHaveAttribute('href', '/tenants')
      await user.click(link)
      expect(onDrillDown).not.toHaveBeenCalled()
      expect(screen.queryByRole('button', { name: /View Security deposits transactions/ })).not.toBeInTheDocument()
    })
  })
})
