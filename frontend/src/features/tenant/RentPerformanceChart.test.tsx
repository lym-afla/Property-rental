import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RentPerformanceChart } from './RentPerformanceChart'
import type { TenantRentPerformanceResponse } from '@/types/analytics'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: ({ tickFormatter }: { tickFormatter: (value: number) => string }) => <span data-testid="rent-negative-axis-tick">{tickFormatter(-1000)}</span>,
  Tooltip: () => null,
  ReferenceLine: () => null,
  Bar: ({ name, fill }: { name: string; fill: string }) => <span data-testid={`rent-bar-${name}`} data-fill={fill}>{name} bars</span>,
  Line: ({ name, strokeDasharray, dot, activeDot }: { name: string; strokeDasharray?: string; dot?: boolean; activeDot?: boolean }) => <span data-testid={`rent-line-${name}`} data-dasharray={strokeDasharray} data-dot={String(dot)} data-active-dot={String(activeDot)}>{name} line</span>,
}))

const data: TenantRentPerformanceResponse = {
  metric: 'tenant_rent_performance',
  grain: 'month',
  currency: 'GBP',
  scale: 1,
  start: '2026-01-01',
  end: '2026-03-31',
  opening_arrears: 50,
  opening_issues: [],
  status: 'ok',
  issues: [],
  series: [
    { key: 'expected', label: 'Expected rent', kind: 'expected' },
    { key: 'received', label: 'Received rent', kind: 'received' },
    { key: 'variance', label: 'Variance', kind: 'variance' },
    { key: 'cumulative_arrears', label: 'Cumulative arrears', kind: 'cumulative' },
  ],
  points: [
    { period_start: '2026-01-01', period_end: '2026-01-31', expected: 1000, received: 900, variance: -100, cumulative_arrears: -150, status: 'ok', issues: [] },
  ],
}

describe('RentPerformanceChart', () => {
  it('uses the server rent-performance values with explicit period and exact table values', async () => {
    const user = userEvent.setup()
    render(<RentPerformanceChart data={data} />)

    expect(screen.getByText('Expected rent line')).toBeInTheDocument()
    expect(screen.getByText('Received rent bars')).toBeInTheDocument()
    expect(screen.getByText('Cumulative arrears line')).toBeInTheDocument()
    expect(screen.getByTestId('rent-bar-Received rent').getAttribute('data-fill')).not.toMatch(/^url\(/)
    expect(screen.getByTestId('rent-bar-Received rent').getAttribute('data-fill')).not.toBe(
      screen.getByTestId('rent-bar-Variance').getAttribute('data-fill'),
    )
    expect(screen.getByTestId('rent-line-Expected rent')).not.toHaveAttribute('data-dasharray')
    expect(screen.getByTestId('rent-line-Cumulative arrears')).not.toHaveAttribute('data-dasharray')
    expect(screen.getByTestId('rent-line-Expected rent')).toHaveAttribute('data-dot', 'false')
    expect(screen.getByTestId('rent-line-Cumulative arrears')).toHaveAttribute('data-dot', 'false')
    expect(screen.getByTestId('rent-line-Expected rent')).toHaveAttribute('data-active-dot', 'false')
    expect(screen.getByTestId('rent-line-Cumulative arrears')).toHaveAttribute('data-active-dot', 'false')
    expect(screen.getByText('Native currency: GBP · Reporting period: 2026-01-01 to 2026-03-31')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Table' }))
    const table = screen.getByRole('table', { name: /tenant rent performance exact values/i })
    expect(table).toHaveTextContent('£1,000')
    expect(table).toHaveTextContent('£900')
    expect(table).toHaveTextContent('(£100)')
    expect(table).toHaveTextContent('(£150)')
  })

  it('formats negative compact axis values with accounting parentheses', () => {
    render(<RentPerformanceChart data={data} />)

    expect(screen.getByTestId('rent-negative-axis-tick')).toHaveTextContent('(£1k)')
  })

  it('renders loading, retryable error, and empty states', () => {
    const { rerender } = render(<RentPerformanceChart isLoading />)
    expect(screen.getByTestId('analytics-chart-skeleton')).toBeInTheDocument()

    rerender(<RentPerformanceChart isError onRetry={() => undefined} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load tenant rent performance.')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()

    rerender(<RentPerformanceChart data={{ ...data, points: [] }} />)
    expect(screen.getByText('No tenant rent-performance data for this selection.')).toBeInTheDocument()
  })
})
