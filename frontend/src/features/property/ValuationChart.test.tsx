import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { parseISO } from 'date-fns'
import { describe, expect, it, vi } from 'vitest'

import { ValuationChart } from './ValuationChart'
import type { PropertyValuationAnalyticsResponse } from '@/types/analytics'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children, data }: { children: React.ReactNode; data: Array<{ timestamp?: number }> }) => (
    <div data-testid="valuation-chart" data-points={JSON.stringify(data)}>{children}</div>
  ),
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: ({ tickFormatter }: { tickFormatter: (value: number) => string }) => <span data-testid="valuation-axis">{tickFormatter(500000)}</span>,
  Tooltip: ({ content }: { content: (props: { active: boolean; label: number; payload: Array<{ name: string; value: number }> }) => React.ReactNode }) => (
    <div data-testid="valuation-tooltip">{content({ active: true, label: parseISO('2018-01-01').getTime(), payload: [{ name: 'Debt', value: -100 }] })}</div>
  ),
  Bar: ({ name, fill }: { name: string; fill: string }) => <span data-testid={`valuation-bar-${name}`} data-fill={fill}>{name} bars</span>,
  Line: ({ name, strokeDasharray, dot }: { name: string; strokeDasharray?: string; dot?: boolean }) => <span data-testid={`valuation-line-${name}`} data-dasharray={strokeDasharray} data-dot={String(dot)}>{name} line</span>,
}))

const data: PropertyValuationAnalyticsResponse = {
  metric: 'property_valuation',
  grain: 'record',
  currency: 'GBP',
  scale: 1,
  start: '2018-01-01',
  end: '2026-07-29',
  status: 'ok',
  series: [
    { key: 'total_value', label: 'Total value', kind: 'total' },
    { key: 'debt', label: 'Debt', kind: 'debt' },
    { key: 'equity', label: 'Equity', kind: 'equity' },
  ],
  points: [
    { period_start: '2018-01-01', period_end: '2018-01-01', total_value: 500000, debt: 200000, equity: 300000, status: 'ok' },
    { period_start: '2026-07-01', period_end: '2026-07-01', total_value: 600000, debt: 180000, equity: 420000, status: 'ok' },
  ],
}

describe('ValuationChart', () => {
  it('keeps all server-provided records and formats compact axis plus exact table values', async () => {
    const user = userEvent.setup()
    render(<ValuationChart data={data} />)

    expect(screen.getByTestId('valuation-axis')).toHaveTextContent('£500k')
    expect(screen.getByText(/All time: 2018-01-01 to 2026-07-29/)).toBeInTheDocument()
    expect(screen.getByTestId('valuation-bar-Debt').getAttribute('data-fill')).not.toMatch(/^url\(/)
    expect(screen.getByTestId('valuation-bar-Debt').getAttribute('data-fill')).not.toBe(
      screen.getByTestId('valuation-bar-Equity').getAttribute('data-fill'),
    )
    expect(screen.getByTestId('valuation-line-Total value')).toHaveAttribute('data-dot', 'false')
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: /property valuation exact values/i })).toHaveTextContent('1 Jan 2018')
    expect(screen.getByRole('table', { name: /property valuation exact values/i })).toHaveTextContent('£500,000')
  })

  it('positions sparse valuation records by their continuous timestamps', () => {
    render(<ValuationChart data={{
      ...data,
      points: [
        { period_start: '2004-01-01', period_end: '2004-01-01', total_value: 300000, debt: 100000, equity: 200000, status: 'ok' },
        { period_start: '2023-01-01', period_end: '2023-01-01', total_value: 500000, debt: 200000, equity: 300000, status: 'ok' },
        { period_start: '2024-01-01', period_end: '2024-01-01', total_value: 600000, debt: 180000, equity: 420000, status: 'ok' },
      ],
    }} />)

    const points = JSON.parse(screen.getByTestId('valuation-chart').dataset.points ?? '[]') as Array<{ timestamp: number }>
    const [x2004, x2023, x2024] = points.map((point) => point.timestamp)
    expect(x2004).toBe(parseISO('2004-01-01').getTime())
    expect(x2023).toBe(parseISO('2023-01-01').getTime())
    expect(x2024).toBe(parseISO('2024-01-01').getTime())
    expect((x2023 - x2004) / (x2024 - x2023)).toBeGreaterThan(18)
  })

  it('uses accounting formatting for negative values in the exact table and tooltip', async () => {
    const user = userEvent.setup()
    render(<ValuationChart data={{
      ...data,
      points: [
        { period_start: '2018-01-01', period_end: '2018-01-01', total_value: 500000, debt: -100, equity: -200, status: 'ok' },
      ],
    }} />)

    expect(within(screen.getByTestId('valuation-tooltip')).getByText('(£100)')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(within(screen.getByRole('table', { name: /property valuation exact values/i })).getByText('(£100)')).toBeVisible()
  })

  it('offers valuation history rather than transaction navigation when no records exist', () => {
    render(<ValuationChart data={{ ...data, points: [], status: 'missing_valuation' }} onViewHistory={() => undefined} />)

    expect(screen.getByRole('button', { name: /view valuation history/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /transactions/i })).not.toBeInTheDocument()
  })

  it('renders loading and retryable error states', () => {
    const { rerender } = render(<ValuationChart isLoading />)
    expect(screen.getByTestId('analytics-chart-skeleton')).toBeInTheDocument()

    rerender(<ValuationChart isError onRetry={() => undefined} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load property valuation.')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})
