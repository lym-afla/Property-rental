// Mirrors `DepositMovementSerializer` in
// `property_rental/rentals/api/serializers.py`. Field names MUST match the
// serializer exactly (snake_case preserved on purpose).
export type DepositKind = 'received' | 'returned' | 'applied'
export type DepositAppliedTo = 'rent' | 'cost_reimbursement'

export type DepositMovement = {
  id: number
  tenant: number
  date: string
  kind: DepositKind
  currency: string
  amount: string // Decimal as string, 2dp
  applied_to: DepositAppliedTo | null
  transaction: number | null
  owns_transaction: boolean // read-only
  comment: string | null
}

// Response of `GET /deposit-movements/balance/`. `by_tenant` is only present
// when queried by property.
export type DepositBalance = {
  as_of: string
  balances: { currency: string; amount: string }[]
  by_tenant?: { tenant: number; currency: string; amount: string }[]
}
