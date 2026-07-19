import type { User } from '@/types/user'

export const fixtureUser: User = {
  id: 1,
  username: 'alice',
  email: 'alice@example.com',
  first_name: 'Alice',
  last_name: 'Smith',
  is_landlord: true,
  is_tenant: false,
  effective_date: null,
  default_currency: 'USD',
  // NOTE: the real User model field is `use_default_currency_for_all_data`
  // (the task brief typo'd `default_currency_for_all_data`, which would fail
  // the TypeScript build against the User type). Aligned to the type here.
  use_default_currency_for_all_data: false,
  chart_frequency: 'M',
  chart_timeline: 'last_6_months',
  digits: 0,
}
