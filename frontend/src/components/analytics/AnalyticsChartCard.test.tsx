import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AnalyticsChartCard } from './AnalyticsChartCard'

const table = {
  columns: [
    { key: 'period', label: 'Period' },
    { key: 'income', label: 'Net income', numeric: true },
  ],
  rows: [{ period: 'Jan 2026', income: '$1,200' }],
}

describe('AnalyticsChartCard', () => {
  it('reserves a fixed chart footprint while loading', () => {
    render(
      <AnalyticsChartCard state={{ status: 'loading' }} title="Net income">
        <div>Rendered chart</div>
      </AnalyticsChartCard>,
    )

    expect(screen.getByTestId('analytics-chart-skeleton')).toHaveClass('h-[300px]')
    expect(screen.queryByText('Rendered chart')).not.toBeInTheDocument()
  })

  it('exposes retry after an error without rendering empty-state copy', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    render(
      <AnalyticsChartCard
        state={{ status: 'error', message: 'Could not load net income.', onRetry: retry }}
        title="Net income"
      >
        <div>Rendered chart</div>
      </AnalyticsChartCard>,
    )

    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(retry).toHaveBeenCalledOnce()
    expect(screen.getByText('Could not load net income.')).toBeInTheDocument()
    expect(screen.queryByText('No data is available for this metric.')).not.toBeInTheDocument()
  })

  it('shows metric-specific empty copy and an optional action', () => {
    render(
      <AnalyticsChartCard
        state={{
          status: 'empty',
          message: 'No occupancy records match these filters.',
          action: <a href="/tenants">Review tenants</a>,
        }}
        title="Occupancy"
      >
        <div>Rendered chart</div>
      </AnalyticsChartCard>,
    )

    expect(screen.getByText('No occupancy records match these filters.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review tenants' })).toHaveAttribute('href', '/tenants')
  })

  it('lets people switch a successful chart to its exact-value table', async () => {
    const user = userEvent.setup()
    render(
      <AnalyticsChartCard state={{ status: 'success' }} title="Net income" table={table}>
        <div>Rendered chart</div>
      </AnalyticsChartCard>,
    )

    await user.click(screen.getByRole('button', { name: 'Table' }))

    expect(screen.getByRole('table', { name: 'Net income exact values' })).toBeInTheDocument()
    expect(screen.getByText('$1,200')).toBeInTheDocument()
    expect(screen.queryByText('Rendered chart')).not.toBeInTheDocument()
  })
})
