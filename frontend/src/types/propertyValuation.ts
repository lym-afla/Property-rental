// Mirrors `PropertyCapitalStructureSerializer` in
// `property_rental/rentals/api/serializers.py` (backing the
// `/api/v1/property-valuations/` endpoint). Field names MUST match the
// serializer exactly (snake_case preserved on purpose).
export type PropertyValuation = {
  id: number
  property: number
  capital_structure_date: string
  capital_structure_value: string
  capital_structure_debt: string
}
