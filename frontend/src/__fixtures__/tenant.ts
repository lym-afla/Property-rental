import type { Tenant, TenantWithStats } from '@/types/tenant'

export const fixtureTenant: Tenant = {
  id: 1,
  user: null,
  property: 1,
  first_name: 'Bob',
  last_name: 'Jones',
  phone: '+49 30 1234567',
  email: 'bob@example.com',
  lease_start: '2024-01-01',
  lease_end: '2024-12-31',
  payday: 1,
}

export const fixtureTenantWithStats: TenantWithStats = {
  ...fixtureTenant,
  rent_rate: '800.00',
  revenue_all_time: 9600,
  revenue_ytd: 4800,
  debt: 0,
  stats_currency: 'USD',
}

// A second tenant tied to property 2, with an open-ended lease
// (lease_end=null) to exercise the nullable branch.
export const fixtureTenantAlt: Tenant = {
  id: 2,
  user: null,
  property: 2,
  first_name: 'Carol',
  last_name: 'Doe',
  phone: '+49 89 9876543',
  email: 'carol@example.com',
  lease_start: '2024-06-01',
  lease_end: null,
  payday: 15,
}
