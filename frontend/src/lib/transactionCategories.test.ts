import { describe, expect, it } from 'vitest'

import { TRANSACTION_CATEGORIES, transactionCategoryLabel } from './transactionCategories'

describe('transactionCategoryLabel', () => {
  it.each([
    ['cost_reimbursement', 'Cost reimbursement'],
    ['other_expenses', 'Other expenses'],
    ['unknown_key', 'Unknown key'],
  ])('formats %s as %s', (key, expected) => {
    expect(transactionCategoryLabel(key)).toBe(expected)
  })

  it('includes rent among the canonical transaction categories', () => {
    expect(TRANSACTION_CATEGORIES.map(({ value }) => value)).toContain('rent')
  })
})
