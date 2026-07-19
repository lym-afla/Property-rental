import type { Transaction } from '@/types/transaction'

export const fixtureTransactionIncome: Transaction = {
  id: 1,
  property: 1,
  tenant: 1,
  date: '2024-01-31',
  category: 'rent',
  period: '2024-01',
  currency: 'EUR',
  amount: '800.00',
  type: 'income',
  comment: 'January rent',
}

export const fixtureTransactionExpense: Transaction = {
  id: 2,
  property: 1,
  tenant: null,
  date: '2024-01-15',
  category: 'repair',
  period: '2024-01',
  currency: 'EUR',
  amount: '-150.00',
  type: 'expense',
  comment: 'Leaking tap fix',
}
