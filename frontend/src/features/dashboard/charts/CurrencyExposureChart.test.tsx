import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CurrencyExposureChart } from './CurrencyExposureChart'

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const data = {
  metric: 'currency_exposure' as const, grain: 'month' as const, currency: 'USD', scale: 1 as const,
  start: '2026-01-01', end: '2026-02-28', measure: 'property_value' as const, measure_label: 'Property value',
  series: [{ key: 'USD', label: 'USD', kind: 'native_currency' }, { key: 'EUR', label: 'EUR', kind: 'native_currency' }],
  points: [
    { period_start: '2026-01-01', period_end: '2026-01-31', USD: 100, EUR: 200 },
    { period_start: '2026-02-01', period_end: '2026-02-28', USD: 150, EUR: 250 },
  ],
  coverage: [],
}

describe('CurrencyExposureChart', () => {
  it('renders exactly one currency bar per period and currency, with a table alternative', async () => {
    const user = userEvent.setup()
    render(<CurrencyExposureChart data={data} measure="property_value" onMeasureChange={vi.fn()} />)

    expect(screen.getAllByTestId(/currency-exposure-bar-/)).toHaveLength(4)
    await user.click(screen.getByRole('button', { name: 'Table' }))
    expect(screen.getByRole('table', { name: 'Currency exposure exact values' })).toBeInTheDocument()
  })

  it('offers a touch-sized URL-owned exposure measure selector at 390 pixels', async () => {
    const user = userEvent.setup()
    const onMeasureChange = vi.fn()
    vi.stubGlobal('innerWidth', 390)
    render(<CurrencyExposureChart data={data} measure="property_value" onMeasureChange={onMeasureChange} />)

    const selector = screen.getByLabelText('Exposure measure')
    expect(selector).toHaveClass('min-h-11')
    await user.selectOptions(selector, 'debt')
    expect(onMeasureChange).toHaveBeenCalledWith('debt')
    vi.unstubAllGlobals()
  })
})
