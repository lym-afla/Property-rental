import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ProfitLossResponse } from '@/types/analytics'
import { ProfitLossTable } from './ProfitLossTable'

const statement: ProfitLossResponse = {
  metric: 'profit_and_loss',
  currency: 'USD',
  scale: 1,
  end: '2026-07-29',
  columns: [
    { key: '2024', label: '2024', start: '2024-01-01', end: '2024-12-31' },
    { key: '2025', label: '2025', start: '2025-01-01', end: '2025-12-31' },
    { key: '2026', label: '2026', start: '2026-01-01', end: '2026-07-29' },
    { key: 'ytd', label: 'YTD', start: '2026-01-01', end: '2026-07-29' },
  ],
  rows: [
    { key: 'rent', label: 'Rental revenue', kind: 'income', values: { '2024': 24000, '2025': 26000, '2026': 14000, ytd: 14000 } },
    { key: 'tax', label: 'Property tax', kind: 'expense', values: { '2024': -2000, '2025': -2100, '2026': 0, ytd: 0 } },
    { key: 'total_revenue', label: 'Total revenue', kind: 'total_revenue', values: { '2024': 24000, '2025': 26000, '2026': 14000, ytd: 14000 } },
    { key: 'total_expenses', label: 'Total expenses', kind: 'total_expenses', values: { '2024': -2000, '2025': -2100, '2026': 0, ytd: 0 } },
    { key: 'net_income', label: 'Net income', kind: 'net_income', values: { '2024': 22000, '2025': 23900, '2026': 14000, ytd: 14000 } },
  ],
}

describe('ProfitLossTable', () => {
  it('renders server labels, chronological years, YTD last, and accounting values', () => {
    render(<ProfitLossTable data={statement} />)

    const table = screen.getByRole('table', { name: 'Profit and Loss statement' })
    expect(within(table).getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
      'Category', '2024', '2025', '2026', 'YTD',
    ])
    expect(within(table).getByText('Rental revenue')).toBeInTheDocument()
    expect(within(table).getByText('Property tax')).toBeInTheDocument()
    expect(within(table).getByRole('rowheader', { name: 'Rental revenue' })).toBeInTheDocument()
    expect(within(within(table).getByRole('row', { name: /Rental revenue/ })).getByText('$24,000')).toBeInTheDocument()
    expect(within(within(table).getByRole('row', { name: /Property tax/ })).getByText('($2,000)')).toBeInTheDocument()
  })

  it('keeps descriptions sticky inside a horizontal scroller and divides totals', () => {
    render(<ProfitLossTable data={statement} />)

    const table = screen.getByRole('table', { name: 'Profit and Loss statement' })
    expect(table.closest('[data-slot="table-container"]')).toHaveClass('overflow-x-auto')
    expect(within(table).getByRole('columnheader', { name: 'Category' })).toHaveClass('sticky', 'left-0')
    expect(within(table).getByText('Rental revenue')).toHaveClass('sticky', 'left-0')
    expect(within(table).getByRole('row', { name: /Total revenue/ })).toHaveClass('border-t', 'font-semibold')
    expect(within(table).getByRole('row', { name: /Net income/ })).toHaveClass('border-t', 'font-semibold')
  })
})
