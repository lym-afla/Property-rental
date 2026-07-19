// Mirrors `TransactionSerializer` in
// `property_rental/rentals/api/serializers.py`. Field names MUST match the
// serializer exactly (snake_case preserved on purpose).
export type Transaction = {
  id: number
  property: number
  tenant: number | null
  date: string
  category: string
  period: string
  currency: string
  amount: string  // Decimal as string
  type: string    // read-only
  comment: string | null
}
