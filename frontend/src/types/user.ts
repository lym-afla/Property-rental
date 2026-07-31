// Mirrors the Django `User` model in `property_rental/rentals/models.py`.
// Field names MUST match the model exactly (snake_case preserved on purpose).
export type User = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_landlord: boolean
  is_tenant: boolean
  effective_date?: string | null  // Development-only ISO date override.
  // Django CharField with blank=True, null=True — may be absent.
  default_currency: string | null
  // NOTE: the plan originally said `default_currency_for_all_data`,
  // but the real model field is `use_default_currency_for_all_data`.
  use_default_currency_for_all_data: boolean
  chart_frequency: 'M' | 'Q' | 'Y'
  chart_timeline: string         // free-form string per Phase 1 model
  digits: number
}
