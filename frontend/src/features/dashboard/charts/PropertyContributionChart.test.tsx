import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PropertyContributionChart } from './PropertyContributionChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const data = {
  metric: 'property_contribution' as const, currency: 'USD', scale: 1 as const,
  start: '2026-01-01', end: '2026-03-31', portfolio_net_income: 500,
  rows: [
    { property_id: 1, property_name: 'Birch House', revenue: 1000, costs: 250, net_income: 750, portfolio_share: 150 },
    { property_id: 2, property_name: 'Canal Court', revenue: 100, costs: 350, net_income: -250, portfolio_share: -50 },
  ],
}

describe('PropertyContributionChart', () => {
  it('preserves negative contributors and exposes signed exact values without hover', async () => {
    const user = userEvent.setup()
    render(<PropertyContributionChart data={data} />)

    expect(screen.getByTestId('property-contribution-2')).toHaveAttribute('data-net-income', '-250')
    expect(screen.getByText('Negative contributor')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Property contribution exact values' })).toHaveTextContent('$-250')
  })

  it('keeps the table control touch-sized at a 390-pixel viewport', () => {
    vi.stubGlobal('innerWidth', 390)
    render(<PropertyContributionChart data={data} />)
    expect(screen.getByRole('button', { name: 'Table' })).toHaveClass('min-h-11')
    vi.unstubAllGlobals()
  })
})
