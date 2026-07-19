import type { Property, PropertyWithStats } from '@/types/property'

export const fixtureProperty: Property = {
  id: 1,
  owned_by: 1,
  name: 'Riverside Flat',
  location: 'Berlin, DE',
  address: 'Hauptstrasse 1',
  num_bedrooms: 2,
  area: '75.50',
  currency: 'EUR',
  sold: null,
}

export const fixturePropertyWithStats: PropertyWithStats = {
  ...fixtureProperty,
  gross_income_all_time: 7200,
  expenses_all_time: 1680,
  net_income_all_time: 8880,
  gross_income_ytd: 3600,
  expenses_ytd: 840,
  net_income_ytd: 4440,
}

// Second property with distinct values so list-rendering tests can assert
// ordering and per-item content unambiguously.
export const fixturePropertyAlt: Property = {
  id: 2,
  owned_by: 1,
  name: 'Lakeside House',
  location: 'Munich, DE',
  address: 'Seestrasse 42',
  num_bedrooms: 4,
  area: '120.00',
  currency: 'EUR',
  sold: '2025-06-30',
}
