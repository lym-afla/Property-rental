import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CurrencyExposureChart } from './CurrencyExposureChart'

vi.mock('@/context/SessionProvider', () => ({
  useSession: () => ({ user: { default_currency: 'USD' } }),
}))

vi.mock('@/api/properties', () => ({
  usePropertiesWithStats: () => ({ data: [], isLoading: true }),
}))

vi.mock('@/api/charts', () => ({
  useChartData: () => ({ data: undefined, isLoading: true }),
}))

describe('CurrencyExposureChart', () => {
  it('uses a 44px timeline control wherever the legacy chart is rendered', () => {
    render(<CurrencyExposureChart />)
    expect(screen.getByLabelText('Currency exposure timeline')).toHaveClass('min-h-11')
  })
})
