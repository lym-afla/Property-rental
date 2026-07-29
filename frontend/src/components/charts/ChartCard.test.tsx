import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ChartCard } from './ChartCard'

describe('ChartCard', () => {
  it('gives the chart/table toggle a 44px touch target', () => {
    render(
      <ChartCard
        title="Performance"
        tableData={{ headers: ['Period'], rows: [['2026-01']] }}
      >
        <div>Chart</div>
      </ChartCard>,
    )
    expect(screen.getByRole('button', { name: 'Table' })).toHaveClass('min-h-11')
  })
})
