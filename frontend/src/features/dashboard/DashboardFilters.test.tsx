import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DashboardFilters } from './DashboardFilters'
import type { DashboardFilterState } from './filters'

const initialFilters: DashboardFilterState = {
  section: 'overview',
  start: '2026-01-01',
  end: '2026-07-29',
  currency: 'USD',
  grain: 'month',
  propertyIds: [],
  exposureMeasure: 'property_value',
}

const properties = [
  { id: 1, name: 'Birch House' },
  { id: 3, name: 'Canal Court' },
]

const originalInnerWidth = window.innerWidth
const originalMatchMedia = window.matchMedia

function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(min-width: 768px)' ? width >= 768 : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn().mockReturnValue(true),
    })),
  })
}

function StatefulFilters({ onReset = vi.fn() }: { onReset?: () => void }) {
  const [filters, setFilters] = useState(initialFilters)
  return (
    <DashboardFilters
      filters={filters}
      properties={properties}
      onChange={setFilters}
      onReset={() => {
        onReset()
        setFilters(initialFilters)
      }}
    />
  )
}

describe('DashboardFilters', () => {
  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: originalInnerWidth,
    })
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: originalMatchMedia,
    })
  })

  it('exposes labelled 44px controls and reports desktop filter changes', async () => {
    const user = userEvent.setup()
    setViewport(1280)
    render(<StatefulFilters />)

    const start = screen.getByLabelText('Start date')
    const end = screen.getByLabelText('As of date')
    const currency = screen.getByLabelText('Reporting currency')
    const grain = screen.getByLabelText('Frequency')
    expect(screen.queryByLabelText('Comparison')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Properties' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Filters' })).not.toBeInTheDocument()

    for (const control of [start, end, currency, grain]) {
      expect(control).toHaveClass('min-h-11')
    }

    await user.clear(start)
    await user.type(start, '2026-02-01')
    expect(start).toHaveValue('2026-02-01')

    await user.click(currency)
    await user.click(screen.getByRole('option', { name: 'GBP' }))
    expect(currency).toHaveTextContent('GBP')

    await user.click(grain)
    await user.click(screen.getByRole('option', { name: 'Quarterly' }))
    expect(grain).toHaveTextContent('Quarterly')
  })

  it('keeps essential controls visible and exposes advanced controls in a bottom sheet', async () => {
    const user = userEvent.setup()
    setViewport(390)
    render(<StatefulFilters />)

    expect(screen.getByLabelText('Start date')).toBeVisible()
    expect(screen.getByLabelText('As of date')).toBeVisible()
    expect(screen.getByLabelText('Reporting currency')).toBeVisible()

    const filtersButton = screen.getByRole('button', { name: 'Filters' })
    expect(filtersButton).toHaveClass('min-h-11')
    await user.click(filtersButton)

    const sheet = screen.getByRole('dialog', { name: 'Dashboard filters' })
    expect(sheet).toHaveAttribute('data-side', 'bottom')

    expect(within(sheet).queryByLabelText('Comparison')).not.toBeInTheDocument()

    await user.click(within(sheet).getByRole('checkbox', { name: 'Birch House' }))
    expect(within(sheet).getByRole('checkbox', { name: 'Birch House' })).toBeChecked()
  })

  it('renders only the usable mobile filter surface at 390px and restores focus on dismissal', async () => {
    const user = userEvent.setup()
    setViewport(390)
    render(<StatefulFilters />)

    const start = screen.getByLabelText('Start date')
    const end = screen.getByLabelText('As of date')
    const currency = screen.getByLabelText('Reporting currency')
    expect(start).toBeVisible()
    expect(end).toBeVisible()
    expect(currency).toBeVisible()
    expect(screen.queryByLabelText('Frequency')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Comparison')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Properties' })).not.toBeInTheDocument()

    await user.clear(start)
    await user.type(start, '2026-02-01')
    expect(start).toHaveValue('2026-02-01')

    await user.click(currency)
    await user.click(screen.getByRole('option', { name: 'EUR' }))
    expect(currency).toHaveTextContent('EUR')

    const trigger = screen.getByRole('button', { name: 'Filters' })
    await user.click(trigger)
    const sheet = screen.getByRole('dialog', { name: 'Dashboard filters' })
    expect(within(sheet).getAllByLabelText('Frequency')).toHaveLength(1)
    expect(within(sheet).queryByLabelText('Comparison')).not.toBeInTheDocument()
    expect(within(sheet).getByRole('checkbox', { name: 'Birch House' })).toBeVisible()
    expect(sheet).toContainElement(document.activeElement as HTMLElement)

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Dashboard filters' })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('provides deterministic reset behavior', async () => {
    const user = userEvent.setup()
    const onReset = vi.fn()
    render(<StatefulFilters onReset={onReset} />)

    await user.click(screen.getByRole('button', { name: 'Reset dashboard filters' }))
    expect(onReset).toHaveBeenCalledOnce()
    expect(screen.getByLabelText('Start date')).toHaveValue('2026-01-01')
  })
})
