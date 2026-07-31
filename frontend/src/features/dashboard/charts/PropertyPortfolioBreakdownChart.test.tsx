import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PropertyPortfolioBreakdownChart } from './PropertyPortfolioBreakdownChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: ({ name, stroke, strokeDasharray, dot, activeDot }: { name: string; stroke?: string; strokeDasharray?: string; dot?: boolean; activeDot?: boolean }) => <span data-testid={`breakdown-line-${name}`} data-color={stroke} data-dasharray={strokeDasharray} data-dot={String(dot)} data-active-dot={String(activeDot)} />,
  XAxis: ({ type }: { type?: string }) => <span data-testid="breakdown-x-axis" data-type={type} />,
}))

const data = {
  metric: 'property_breakdown' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const,
  start: '2026-01-01', end: '2026-02-28', measure: 'property_value' as const, measure_label: 'Property value',
  series: [{ key: 'property_1', label: 'Anokhina', kind: 'property' }, { key: 'property_2', label: 'Wandsworth', kind: 'property' }],
  points: [
    { period_start: '2026-01-01', period_end: '2026-01-31', property_1: 100, property_2: 200 },
    { period_start: '2026-02-01', period_end: '2026-02-28', property_1: 150, property_2: 250 },
  ],
  coverage: [
    { period_start: '2026-01-01', period_end: '2026-01-31', property_id: 1, status: 'ok' as const },
    { period_start: '2026-01-01', period_end: '2026-01-31', property_id: 2, status: 'ok' as const },
  ],
}

describe('PropertyPortfolioBreakdownChart', () => {
  it('renders one distinct solid line per property on a continuous timeline', () => {
    render(<PropertyPortfolioBreakdownChart data={data} measure="property_value" onMeasureChange={vi.fn()} />)

    const lines = screen.getAllByTestId(/breakdown-line-/)
    expect(lines).toHaveLength(2)
    expect(lines.map((line) => line.dataset.color)).toEqual(['#2563EB', '#D97706'])
    expect(lines.every((line) => line.dataset.dasharray === undefined)).toBe(true)
    expect(lines.every((line) => line.dataset.dot === 'false')).toBe(true)
    expect(lines.every((line) => line.dataset.activeDot === 'false')).toBe(true)
    expect(screen.getByTestId('breakdown-x-axis')).toHaveAttribute('data-type', 'number')
    expect(screen.getByTestId('property-breakdown-plot')).toHaveClass('min-w-[320px]')
    expect(screen.getByRole('group', { name: 'Chart series' })).toHaveClass('flex-wrap')
  })

  it('exposes property exact values without hover', async () => {
    const user = userEvent.setup()
    render(<PropertyPortfolioBreakdownChart data={data} measure="property_value" onMeasureChange={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Table' }))
    const table = screen.getByRole('table', { name: 'Portfolio breakdown by property exact values' })
    expect(table).toHaveTextContent('Anokhina')
    expect(table).toHaveTextContent('$100')
  })

  it('omits post-sale property rows when the backend omits the point key', async () => {
    const user = userEvent.setup()
    const withSale = {
      ...data,
      points: [
        data.points[0],
        { period_start: '2026-02-01', period_end: '2026-02-28', property_2: 250 },
      ],
    }
    render(<PropertyPortfolioBreakdownChart data={withSale} measure="property_value" onMeasureChange={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Table' }))
    const table = screen.getByRole('table', { name: 'Portfolio breakdown by property exact values' })
    expect(table.querySelectorAll('tbody tr')).toHaveLength(3)
    expect(table).not.toHaveTextContent('Feb 1, 2026Anokhina')
  })

  it('assigns a distinct solid color to properties beyond the base token palette', () => {
    const series = Array.from({ length: 10 }, (_, index) => ({
      key: `property_${index + 1}`,
      label: `Property ${index + 1}`,
      kind: 'property',
    }))
    const points = [{
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      ...Object.fromEntries(series.map((item, index) => [item.key, index + 1])),
    }]
    render(<PropertyPortfolioBreakdownChart data={{ ...data, series, points }} measure="property_value" onMeasureChange={vi.fn()} />)

    const colors = screen.getAllByTestId(/breakdown-line-/).map((line) => line.dataset.color)
    expect(new Set(colors).size).toBe(10)
    expect(colors.every((color) => color && !color.startsWith('url('))).toBe(true)
  })

  it('offers equity in the touch-sized URL-owned measure selector at 390 pixels', async () => {
    const user = userEvent.setup()
    const onMeasureChange = vi.fn()
    vi.stubGlobal('innerWidth', 390)
    render(<PropertyPortfolioBreakdownChart data={data} measure="property_value" onMeasureChange={onMeasureChange} />)

    const selector = screen.getByLabelText('Portfolio breakdown measure')
    expect(selector).toHaveClass('min-h-11')
    await user.selectOptions(selector, 'equity')
    expect(onMeasureChange).toHaveBeenCalledWith('equity')
    vi.unstubAllGlobals()
  })
})
