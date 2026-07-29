import { describe, expect, it } from 'vitest'

import {
  parseDashboardFilters,
  serializeDashboardFilters,
  type DashboardFilterState,
} from './filters'

const defaults: DashboardFilterState = {
  section: 'overview',
  start: '2026-01-01',
  end: '2026-07-29',
  currency: 'USD',
  grain: 'month',
  comparison: null,
  propertyIds: [],
  exposureMeasure: 'property_value',
}

describe('dashboard URL filters', () => {
  it('round-trips section, range, currency, grain, comparison, and properties', () => {
    const parsed = parseDashboardFilters(
      new URLSearchParams(
        'section=portfolio&start=2026-01-01&end=2026-07-29&currency=GBP&grain=quarter&comparison=previous_period&property=3&property=1&property=3&measure=debt',
      ),
      defaults,
    )

    expect(parsed).toEqual({
      section: 'portfolio',
      start: '2026-01-01',
      end: '2026-07-29',
      currency: 'GBP',
      grain: 'quarter',
      comparison: 'previous_period',
      propertyIds: [1, 3],
      exposureMeasure: 'debt',
    })
    expect(serializeDashboardFilters(parsed).toString()).toBe(
      'section=portfolio&start=2026-01-01&end=2026-07-29&currency=GBP&grain=quarter&comparison=previous_period&property=1&property=3&measure=debt',
    )
  })

  it('falls invalid values back independently without changing valid values', () => {
    expect(
      parseDashboardFilters(
        new URLSearchParams(
          'section=unknown&start=not-a-date&end=2026-06-30&currency=GBP&grain=week&comparison=bogus&property=2&property=0&property=abc&measure=rental_income',
        ),
        defaults,
      ),
    ).toEqual({
      ...defaults,
      end: '2026-06-30',
      currency: 'GBP',
      propertyIds: [2],
      exposureMeasure: 'rental_income',
    })
  })

  it('falls an inverted range back to the complete default range', () => {
    expect(
      parseDashboardFilters(
        new URLSearchParams('start=2026-08-01&end=2026-07-01'),
        defaults,
      ),
    ).toMatchObject({ start: defaults.start, end: defaults.end })
  })

  it('falls year-zero URL dates back to authenticated defaults', () => {
    expect(
      parseDashboardFilters(
        new URLSearchParams('start=0000-01-01&end=2026-06-30'),
        defaults,
      ),
    ).toMatchObject({ start: defaults.start, end: '2026-06-30' })
  })

  it('serializes defaults explicitly so a copied URL restores the same view', () => {
    expect(serializeDashboardFilters(defaults).toString()).toBe(
      'section=overview&start=2026-01-01&end=2026-07-29&currency=USD&grain=month&comparison=none&property=&measure=property_value',
    )
  })

  it('returns normalized copies rather than mutating authenticated defaults', () => {
    const propertyIds = [5, 2, 5]
    const withProperties = { ...defaults, propertyIds }
    const parsed = parseDashboardFilters(new URLSearchParams(), withProperties)

    expect(parsed.propertyIds).toEqual([2, 5])
    expect(parsed.propertyIds).not.toBe(propertyIds)
    expect(propertyIds).toEqual([5, 2, 5])
  })

  it('encodes explicit none and empty selections when they differ from defaults', () => {
    const authenticatedDefaults: DashboardFilterState = {
      ...defaults,
      comparison: 'previous_period',
      propertyIds: [4],
    }
    const filters: DashboardFilterState = {
      ...authenticatedDefaults,
      comparison: null,
      propertyIds: [],
    }

    const serialized = serializeDashboardFilters(filters)
    expect(
      parseDashboardFilters(serialized, authenticatedDefaults),
    ).toEqual(filters)
  })
})
