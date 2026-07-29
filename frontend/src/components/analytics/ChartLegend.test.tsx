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
        series={[{ key: 'revenue', label: 'Revenue', kind: 'income' }]}
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
})
