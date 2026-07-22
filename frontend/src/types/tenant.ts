// Mirrors `TenantSerializer` in
// `property_rental/rentals/api/serializers.py`. Field names MUST match the
// serializer exactly (snake_case preserved on purpose).
export type Tenant = {
  id: number
  user: number | null
  property: number
  first_name: string
  last_name: string
  phone: string
  email: string
  lease_start: string
  lease_end: string | null
  payday: number
}

export type TenantWithStats = Tenant & {
  rent_rate: number | string
  revenue_all_time: number
  revenue_ytd: number
  debt: number
  // Currency the aggregate fields above are denominated in (almost always
  // `USD` — the backend FX-converts stats to a single target currency).
  // The tenant's NATIVE currency is the property's `currency` field, which
  // is fetched separately via `useProperties`.
  stats_currency: string
}
