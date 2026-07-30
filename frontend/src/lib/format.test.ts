import { describe, expect, it } from 'vitest'

import { formatAccounting } from './format'

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
