export const DASHBOARD_SECTIONS = [
  'overview',
  'income-costs',
  'portfolio',
  'risk',
] as const
export const DASHBOARD_GRAINS = ['month', 'quarter', 'year'] as const
export const DASHBOARD_CURRENCIES = ['USD', 'EUR', 'GBP', 'RUB'] as const
export const DASHBOARD_COMPARISONS = ['previous_period'] as const
export const EXPOSURE_MEASURES = [
  'property_value',
  'debt',
  'rental_income',
] as const

export type DashboardSection = (typeof DASHBOARD_SECTIONS)[number]
export type DashboardGrain = (typeof DASHBOARD_GRAINS)[number]
export type DashboardCurrency = (typeof DASHBOARD_CURRENCIES)[number]
export type DashboardComparison = (typeof DASHBOARD_COMPARISONS)[number]
export type DashboardExposureMeasure = (typeof EXPOSURE_MEASURES)[number]

export type DashboardFilterState = {
  section: DashboardSection
  start: string
  end: string
  currency: DashboardCurrency
  grain: DashboardGrain
  comparison: DashboardComparison | null
  propertyIds: number[]
  exposureMeasure: DashboardExposureMeasure
}

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function isIsoDate(value: string | null): value is string {
  if (value === null || !ISO_DATE_PATTERN.test(value)) return false
  const parsed = new Date(`${value}T00:00:00.000Z`)
  return (
    !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value
  )
}

function isOneOf<T extends string>(
  value: string | null,
  choices: readonly T[],
): value is T {
  return value !== null && choices.includes(value as T)
}

function normalizedPropertyIds(values: readonly number[]): number[] {
  return [
    ...new Set(values.filter(Number.isInteger).filter((id) => id > 0)),
  ].sort((left, right) => left - right)
}

export function parseDashboardFilters(
  searchParams: URLSearchParams,
  defaults: DashboardFilterState,
): DashboardFilterState {
  const sectionValue = searchParams.get('section')
  const startValue = searchParams.get('start')
  const endValue = searchParams.get('end')
  const currencyValue = searchParams.get('currency')?.toUpperCase() ?? null
  const grainValue = searchParams.get('grain')
  const comparisonValue = searchParams.get('comparison')
  const measureValue = searchParams.get('measure')

  let start = isIsoDate(startValue) ? startValue : defaults.start
  let end = isIsoDate(endValue) ? endValue : defaults.end
  if (end < start) {
    start = defaults.start
    end = defaults.end
  }

  const rawPropertyIds = searchParams.has('property')
    ? searchParams
        .getAll('property')
        .map((value) => Number(value))
        .filter(Number.isInteger)
    : defaults.propertyIds

  return {
    section: isOneOf(sectionValue, DASHBOARD_SECTIONS)
      ? sectionValue
      : defaults.section,
    start,
    end,
    currency: isOneOf(currencyValue, DASHBOARD_CURRENCIES)
      ? currencyValue
      : defaults.currency,
    grain: isOneOf(grainValue, DASHBOARD_GRAINS)
      ? grainValue
      : defaults.grain,
    comparison:
      comparisonValue === 'none'
        ? null
        : isOneOf(comparisonValue, DASHBOARD_COMPARISONS)
          ? comparisonValue
          : defaults.comparison,
    propertyIds: normalizedPropertyIds(rawPropertyIds),
    exposureMeasure: isOneOf(measureValue, EXPOSURE_MEASURES)
      ? measureValue
      : defaults.exposureMeasure,
  }
}

export function serializeDashboardFilters(
  filters: DashboardFilterState,
): URLSearchParams {
  const searchParams = new URLSearchParams()
  searchParams.set('section', filters.section)
  searchParams.set('start', filters.start)
  searchParams.set('end', filters.end)
  searchParams.set('currency', filters.currency)
  searchParams.set('grain', filters.grain)
  searchParams.set('comparison', filters.comparison ?? 'none')
  const propertyIds = normalizedPropertyIds(filters.propertyIds)
  for (const propertyId of propertyIds) {
    searchParams.append('property', String(propertyId))
  }
  if (propertyIds.length === 0) searchParams.append('property', '')
  searchParams.set('measure', filters.exposureMeasure)
  return searchParams
}
