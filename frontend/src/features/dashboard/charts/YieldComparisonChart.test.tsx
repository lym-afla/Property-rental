import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { YieldComparisonChart } from './YieldComparisonChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const data = {
  metric: 'property_yields' as const, currency: 'USD', scale: 1 as const,
  start: '2026-01-01', end: '2026-03-31',
  rows: [
    { property_id: 1, property_name: 'Birch House', valuation_date: '2026-03-01', property_value: 100000, annualized_revenue: 7000, annualized_costs: 2000, gross_yield: 7, net_yield: 5, status: 'ok' as const },
    { property_id: 2, property_name: 'Canal Court', valuation_date: null, property_value: null, annualized_revenue: 3000, annualized_costs: 1000, gross_yield: null, net_yield: null, status: 'missing_valuation' as const },
  ],
}

describe('YieldComparisonChart', () => {
  it('shows missing valuations without fabricating a yield point', async () => {
    const user = userEvent.setup()
    render(<YieldComparisonChart data={data} />)

    expect(screen.queryByTestId('yield-point-2-gross')).not.toBeInTheDocument()
    expect(screen.getByTestId('yield-status-2')).toHaveTextContent('Missing valuation')
    expect(screen.getByTestId('missing-valuation-callout')).toBeVisible()
    expect(screen.getByTestId('missing-valuation-callout')).toHaveTextContent('Canal Court')
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Yield comparison exact values' })).toHaveTextContent('Missing valuation')
  })

  it('keeps the gross and net legend wrapped and available at 390 pixels', () => {
    vi.stubGlobal('innerWidth', 390)
    render(<YieldComparisonChart data={data} />)
    expect(screen.getByRole('group', { name: 'Chart series' })).toHaveClass('flex-wrap')
    expect(screen.getByRole('button', { name: 'Gross yield' })).toHaveClass('min-h-11')
    vi.unstubAllGlobals()
  })
})
