// Mirrors `LeaseRentSerializer` in
// `property_rental/rentals/api/serializers.py` (backing the
// `/api/v1/lease-rents/` endpoint). Field names MUST match the serializer
// exactly (snake_case preserved on purpose).
//
// The `Lease_rent` Django model stores a tenant's rent rate history: each
// row is an effective-date entry ("as of <date_rent_set>, rent was <rent>
// <currency>"). The current rate is the row with the latest
// `date_rent_set` <= today (see `Tenant.lease_rent` in
// `rentals/models.py`).
export type LeaseRent = {
  id: number
  tenant: number
  date_rent_set: string
  rent: string  // Decimal as string (matches DecimalField serialization)
  currency: string
}
