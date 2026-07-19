// Mirrors `FXSerializer` in
// `property_rental/rentals/api/serializers.py`. Field names MUST match the
// serializer exactly (snake_case preserved on purpose).
export type FX = {
  id: number
  date: string
  from_currency: string
  to_currency: string
  rate: string  // Decimal as string
}
