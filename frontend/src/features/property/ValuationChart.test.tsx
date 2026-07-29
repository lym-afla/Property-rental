import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ValuationChart } from './ValuationChart'
import type { PropertyValuationAnalyticsResponse } from '@/types/analytics'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: ({ tickFormatter }: { tickFormatter: (value: number) => string }) => <span data-testid="valuation-axis">{tickFormatter(500000)}</span>,
  Tooltip: () => null,
  Bar: ({ name }: { name: string }) => <span>{name} bars</span>,
  Line: ({ name }: { name: string }) => <span>{name} line</span>,
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
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: /property valuation exact values/i })).toHaveTextContent('1 Jan 2018')
    expect(screen.getByRole('table', { name: /property valuation exact values/i })).toHaveTextContent('£500,000')
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
