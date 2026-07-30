import { render } from '@testing-library/react'
import { LineChart } from 'recharts'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ResponsiveChartContainer } from './ResponsiveChartContainer'

describe('ResponsiveChartContainer', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('starts charts with a positive footprint before ResizeObserver reports layout', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    render(
      <div style={{ height: 300, width: 480 }}>
        <ResponsiveChartContainer>
          <LineChart data={[]} />
        </ResponsiveChartContainer>
      </div>,
    )

    expect(
      warn.mock.calls.some(([message]) => String(message).includes('width(-1) and height(-1)')),
    ).toBe(false)
  })
})
