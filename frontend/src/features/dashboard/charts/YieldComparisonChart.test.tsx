import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { PropertyYieldsResponse } from '@/types/analytics'

import { YieldComparisonChart } from './YieldComparisonChart'
import { yieldTooltipRows } from './yieldTooltipRows'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ScatterChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Scatter: ({ name, fill, shape, data = [] }: { name: string; fill?: string; shape?: string; data?: Array<{ property_name: string; yield: number }> }) => <span data-testid={`yield-${name}`} data-fill={fill} data-shape={shape}>{data.map((point) => `${point.property_name} ${point.yield}%`).join(', ')}</span>,
  Tooltip: ({ content }: { content: (props: { active: boolean; payload: Array<{ name: string; value: unknown; payload: { property_name: string } }> }) => React.ReactNode }) => content({ active: true, payload: [{ name: 'Missing', value: null, payload: { property_name: 'Birch House' } }, { name: 'Invalid', value: Number.NaN, payload: { property_name: 'Birch House' } }] }),
}))

const data = {
  metric: 'property_yields' as const, currency: 'USD', scale: 1 as const,
  start: '2026-01-01', end: '2026-03-31',
  rows: [
    { property_id: 1, property_name: 'Birch House', valuation_date: '2026-03-01', property_value: 100000, debt: 40000, equity: 60000, annualized_revenue: 7000, annualized_costs: 2000, gross_yield: 7, equity_yield: 8.33, status: 'ok' as const },
    { property_id: 2, property_name: 'Canal Court', valuation_date: null, property_value: null, debt: null, equity: null, annualized_revenue: 3000, annualized_costs: 1000, gross_yield: null, equity_yield: null, status: 'missing_valuation' as const },
    { property_id: 3, property_name: 'Invalid Heights', valuation_date: '2026-03-01', property_value: 100000, debt: 40000, equity: 60000, annualized_revenue: 0, annualized_costs: 0, gross_yield: Number.NaN, equity_yield: undefined, status: 'ok' as const },
    { property_id: 4, property_name: 'Debt Gap', valuation_date: '2026-03-01', property_value: 100000, debt: null, equity: null, annualized_revenue: 6000, annualized_costs: 1000, gross_yield: 6, equity_yield: null, status: 'missing_valuation' as const },
  ],
} as unknown as PropertyYieldsResponse

describe('YieldComparisonChart', () => {
  it('filters non-yield rows from the tooltip', () => {
    expect(yieldTooltipRows([
      { name: 'Property', dataKey: 'property_name', value: 'Anokhina' },
      { name: 'Gross yield', dataKey: 'yield', value: 8.5 },
    ] as never)).toEqual([
      { label: 'Gross yield', value: '8.5%' },
    ])
  })

  it('shows missing valuations without fabricating a yield point', async () => {
    const user = userEvent.setup()
    render(<YieldComparisonChart data={data} />)

    expect(screen.queryByTestId('yield-point-2-gross')).not.toBeInTheDocument()
    expect(screen.getByTestId('yield-status-2')).toHaveTextContent('Missing valuation')
    expect(screen.getByTestId('missing-valuation-callout')).toBeVisible()
    expect(screen.getByTestId('missing-valuation-callout')).toHaveTextContent('Canal Court')
    expect(screen.getByTestId('missing-valuation-callout')).toHaveTextContent('Canal Court: no yield plotted')
    expect(screen.getByTestId('missing-valuation-callout')).toHaveTextContent('Debt Gap: equity yield not plotted')
    expect(screen.getByTestId('missing-valuation-callout')).not.toHaveTextContent('Debt Gap: no yield plotted')
    expect(screen.getByTestId('yield-point-4-gross')).toHaveTextContent('Gross 6%')
    expect(screen.queryByTestId('yield-point-4-equity')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Yield comparison exact values' })).toHaveTextContent('Missing valuation')
  })

  it('keeps the gross and equity legend wrapped and available at 390 pixels', () => {
    vi.stubGlobal('innerWidth', 390)
    render(<YieldComparisonChart data={data} />)
    expect(screen.getByRole('group', { name: 'Chart series' })).toHaveClass('flex-wrap')
    expect(screen.getByRole('button', { name: 'Gross yield' })).toHaveClass('min-h-11')
    vi.unstubAllGlobals()
  })

  it('uses distinct solid colors without category marker shapes', () => {
    render(<YieldComparisonChart data={data} />)
    expect(screen.getByTestId('yield-Gross yield')).not.toHaveAttribute('data-shape')
    expect(screen.getByTestId('yield-Gross yield').getAttribute('data-fill')).not.toBe(
      screen.getByTestId('yield-Equity yield').getAttribute('data-fill'),
    )
  })

  it('only materializes finite points and labels the tooltip with the property', () => {
    render(<YieldComparisonChart data={data} />)

    expect(screen.getByTestId('yield-Gross yield')).toHaveTextContent('Birch House 7%')
    expect(screen.getByTestId('yield-Equity yield')).toHaveTextContent('Birch House 8.33%')
    expect(screen.getByTestId('yield-Gross yield')).not.toHaveTextContent('Invalid Heights')
    expect(screen.getByTestId('yield-Equity yield')).not.toHaveTextContent('Invalid Heights')
    expect(screen.getByText('Birch House')).toBeInTheDocument()
    expect(screen.queryByText(/Property NaN%/)).not.toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })

  it('places the yield definitions control in the chart header', () => {
    render(<YieldComparisonChart data={data} />)

    expect(screen.getByRole('button', { name: 'Yield definitions' })).toHaveClass('min-h-11', 'min-w-11')
  })
})
