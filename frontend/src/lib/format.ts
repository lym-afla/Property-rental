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
  const magnitude = Math.abs(value)
  const rendered = magnitude >= 1000
    ? `${(magnitude / 1000).toFixed(0)}k`
    : magnitude.toLocaleString(undefined, { maximumFractionDigits: 0 })
  const amount = `${symbol}${rendered}`
  return value < 0 ? `(${amount})` : amount
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$', EUR: '€', GBP: '£', RUB: '₽',
}

// Accounting format: negative numbers render as `(₽1,234)` instead of
// `-₽1,234`. Used in the Transactions table Amount column so expenses
// are visually distinct from the unary-minus style.
export function formatAccounting(
  value: number | string | null | undefined,
  currency: string,
): string {
  if (value === null || value === undefined) return '—'
  const amount = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(amount)) return '—'
  const rendered = `${CURRENCY_SYMBOLS[currency] ?? ''}${Math.abs(amount).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  return amount < 0 ? `(${rendered})` : rendered
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
