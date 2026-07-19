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
}
