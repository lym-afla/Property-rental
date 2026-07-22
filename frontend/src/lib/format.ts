export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

// Format a currency amount with thousands separators (`#,###`). Always uses
// the full-precision representation — the `k` compact form is reserved for
// chart AXIS labels (`formatCurrencyAxis`), per the dashboard redesign
// (KPI cards, tooltips, and table values must show the real number).
export function formatCurrency(
  amount: number | null | undefined,
  currency: string,
): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '—'
  const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', RUB: '₽' }
  const symbol = symbols[currency] ?? ''
  return `${symbol}${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

// Compact axis formatter: collapses amounts >= 1000 to `k` (e.g.
// `$12k`). Reserved for chart axes ONLY — every other surface
// (KPI cards, tooltips, table values) must use `formatCurrency` so the
// real number stays visible.
export function formatCurrencyAxis(value: number, currency: string): string {
  const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', RUB: '₽' }
  const symbol = symbols[currency] ?? ''
  if (Math.abs(value) >= 1000) return `${symbol}${(value / 1000).toFixed(0)}k`
  return `${symbol}${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

// Accounting format: negative numbers render as `₽(1,234)` instead of
// `-₽1,234`. Used in the Transactions table Amount column so expenses
// are visually distinct from the unary-minus style. The value is signed
// (positive = income / asset, negative = expense / liability); pass a
// string (decimal from the API) or a number. The currency symbol is
// always prepended (outside the parentheses for negatives) so the sign
// convention stays unambiguous regardless of the row's currency.
export function formatAccounting(
  value: number | string | null | undefined,
  currency: string,
): string {
  if (value === null || value === undefined) return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (Number.isNaN(num)) return '—'
  const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', RUB: '₽' }
  const symbol = symbols[currency] ?? ''
  const abs = Math.abs(num).toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (num < 0) return `${symbol}(${abs})`
  return `${symbol}${abs}`
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
