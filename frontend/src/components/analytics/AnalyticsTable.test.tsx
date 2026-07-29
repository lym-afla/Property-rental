import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AnalyticsTable } from './AnalyticsTable'

describe('AnalyticsTable', () => {
  it('right-aligns numeric values and keeps the first column sticky in its overflow container', () => {
    render(
      <AnalyticsTable
        label="Net income exact values"
        columns={[
          { key: 'period', label: 'Period' },
          { key: 'income', label: 'Net income', numeric: true },
        ]}
        rows={[{ period: 'Jan 2026', income: '$1,200' }]}
      />,
    )

    expect(screen.getByText('$1,200')).toHaveClass('text-right')
    expect(screen.getByRole('columnheader', { name: 'Period' })).toHaveClass('sticky', 'left-0')
    expect(screen.getByTestId('analytics-table-overflow')).toHaveClass('overflow-x-auto')
  })
})
