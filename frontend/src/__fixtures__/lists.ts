// Barrel-style arrays of the per-entity fixtures, for list-rendering tests
// and MSW handlers that need to return collections.
import type { FX } from '@/types/fx'
import type { Property, PropertyWithStats } from '@/types/property'
import type { PropertyValuation } from '@/types/propertyValuation'
import type { Tenant, TenantWithStats } from '@/types/tenant'
import type { Transaction } from '@/types/transaction'

import { fixtureFX, fixtureFXAlt } from './fx'
import { fixtureProperty, fixturePropertyAlt, fixturePropertyWithStats } from './property'
import {
  fixturePropertyValuation,
  fixturePropertyValuationAlt,
} from './propertyValuation'
import { fixtureTenant, fixtureTenantAlt, fixtureTenantWithStats } from './tenant'
import {
  fixtureTransactionExpense,
  fixtureTransactionIncome,
} from './transaction'

export const fixtureProperties: Property[] = [fixtureProperty, fixturePropertyAlt]

export const fixturePropertiesWithStats: PropertyWithStats[] = [
  fixturePropertyWithStats,
  { ...fixturePropertyAlt,
    gross_income_all_time: 14400,
    expenses_all_time: 2400,
    net_income_all_time: 12000,
    gross_income_ytd: 7200,
    expenses_ytd: 1200,
    net_income_ytd: 6000 },
]

export const fixtureTenants: Tenant[] = [fixtureTenant, fixtureTenantAlt]

export const fixtureTenantsWithStats: TenantWithStats[] = [
  fixtureTenantWithStats,
  { ...fixtureTenantAlt,
    rent_rate: '1200.00',
    revenue_all_time: 7200,
    revenue_ytd: 3600,
    debt: 0 },
]

export const fixtureTransactions: Transaction[] = [
  fixtureTransactionIncome,
  fixtureTransactionExpense,
]

export const fixtureFXList: FX[] = [fixtureFX, fixtureFXAlt]

export const fixturePropertyValuations: PropertyValuation[] = [
  fixturePropertyValuation,
  fixturePropertyValuationAlt,
]
