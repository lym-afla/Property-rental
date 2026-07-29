import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ChartLegend } from './ChartLegend'

describe('ChartLegend', () => {
  it('provides keyboard-operable pressed buttons for each series', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    render(
      <ChartLegend
        series={[{ key: 'revenue', label: 'Revenue', kind: 'primary' }]}
        hiddenKeys={new Set()}
        onToggle={onToggle}
      />,
    )

    const revenue = screen.getByRole('button', { name: 'Revenue' })
    expect(revenue).toHaveAttribute('aria-pressed', 'true')

    revenue.focus()
    await user.keyboard('{Enter}')

    expect(onToggle).toHaveBeenCalledWith('revenue')
  })

  it('reflects controlled hidden keys and exposes a non-color marker', () => {
    const series = [{ key: 'comparison', label: 'Comparison', kind: 'comparison', visualToken: 'secondary' as const }]
    const { rerender } = render(
      <ChartLegend series={series} hiddenKeys={new Set()} onToggle={() => {}} />,
    )

    const comparison = screen.getByRole('button', { name: 'Comparison' })
    expect(comparison).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('legend-marker-comparison')).toHaveAttribute('data-marker', 'square')

    rerender(
      <ChartLegend series={series} hiddenKeys={new Set(['comparison'])} onToggle={() => {}} />,
    )

    expect(screen.getByRole('button', { name: 'Comparison' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('Comparison')).toHaveClass('line-through')
  })
})
