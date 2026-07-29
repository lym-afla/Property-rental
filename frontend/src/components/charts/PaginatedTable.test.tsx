import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PaginatedTable } from './PaginatedTable'

describe('PaginatedTable', () => {
  it('gives dashboard pagination controls 44px touch targets', () => {
    render(<PaginatedTable headers={['Period']} rows={[['2026-01']]} />)
    expect(screen.getByRole('button', { name: 'Previous' })).toHaveClass('min-h-11')
    expect(screen.getByRole('button', { name: 'Next' })).toHaveClass('min-h-11')
  })
})
