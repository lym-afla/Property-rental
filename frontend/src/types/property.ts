// Mirrors `PropertySerializer` in
// `property_rental/rentals/api/serializers.py`. Field names MUST match the
// serializer exactly (snake_case preserved on purpose).
export type Property = {
  id: number
  owned_by: number
  name: string
  location: string
  address: string
  num_bedrooms: number
  area: string | null
  currency: string
  sold: string | null
}

export type PropertyWithStats = Property & {
  gross_income_all_time: number
  expenses_all_time: number
  net_income_all_time: number
  gross_income_ytd: number
  expenses_ytd: number
  net_income_ytd: number
  // Currency the aggregate fields above are denominated in (almost always
  // `USD` — the backend FX-converts stats to a single target currency).
  // Kept separate from the property's native `currency` (RUB/GBP/etc.) so
  // the UI can group by native currency AND format the USD values with the
  // correct symbol.
  stats_currency: string
}
