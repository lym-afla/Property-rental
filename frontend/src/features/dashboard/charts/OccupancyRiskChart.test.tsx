import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { OccupancyRiskChart } from './OccupancyRiskChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const data = {
  metric: 'portfolio_occupancy' as const, grain: 'month' as const, currency: null, scale: 1 as const,
  start: '2026-01-01', end: '2026-02-28',
  series: [
    { key: 'capacity', label: 'Capacity', kind: 'capacity' }, { key: 'occupied', label: 'Occupied', kind: 'occupied' },
    { key: 'vacant', label: 'Vacant', kind: 'vacant' }, { key: 'occupancy_rate', label: 'Occupancy rate', kind: 'percentage' },
  ],
  points: [
    { period_start: '2026-01-01', period_end: '2026-01-31', capacity: 2, occupied: 2, vacant: 0, occupancy_rate: 100 },
    { period_start: '2026-02-01', period_end: '2026-02-28', capacity: 2, occupied: 1, vacant: 1, occupancy_rate: 50 },
  ],
}

describe('OccupancyRiskChart', () => {
  it('does not render occupancy above the server-provided 100-percent maximum', async () => {
    const user = userEvent.setup()
    render(<OccupancyRiskChart data={data} />)

    expect(screen.getByTestId('occupancy-rate-2026-01-01')).toHaveAttribute('data-rate', '100')
    expect(screen.queryByText('101%')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Occupancy risk exact values' })).toHaveTextContent('100%')
  })

  it('keeps capacity context and a touch-sized table control available at 390 pixels', () => {
    vi.stubGlobal('innerWidth', 390)
    render(<OccupancyRiskChart data={data} />)
    expect(screen.getByText('Vacant and capacity context is supplied by the occupancy endpoint.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Table' })).toHaveClass('min-h-11')
    vi.unstubAllGlobals()
  })
})
