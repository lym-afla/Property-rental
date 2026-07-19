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
}
