import { describe, expect, it } from 'vitest'

import { formatAccounting, formatCurrency } from './format'

describe('formatCurrency', () => {
  it('uses accounting notation for negative monetary values', () => {
    expect(formatCurrency(-1234, 'USD')).toBe('($1,234)')
  })
})

describe('formatAccounting', () => {
  it.each([
    [-1234, 'USD', '($1,234)'],
    [-1234, 'GBP', '(£1,234)'],
    [-1234, 'RUB', '(₽1,234)'],
    [1234, 'USD', '$1,234'],
    [null, 'USD', '—'],
    [Number.NaN, 'USD', '—'],
  ] as const)('formats %s in %s as %s', (value, currency, expected) => {
    expect(formatAccounting(value, currency)).toBe(expected)
  })
})
