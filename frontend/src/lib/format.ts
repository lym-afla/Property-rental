export function formatCurrency(
  amount: number | null | undefined,
  currency: string,
  opts: { compact?: boolean } = {}
): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '—'
  const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', RUB: '₽' }
  const symbol = symbols[currency] ?? ''
  if (opts.compact && Math.abs(amount) >= 1000) {
    return `${symbol}${(amount / 1000).toFixed(1)}k`
  }
  return `${symbol}${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
