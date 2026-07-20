// Category → color mapping for consistent chart styling.
export const CATEGORY_COLORS: Record<string, string> = {
  rent: '#22c55e',      // green
  utilities: '#3b82f6', // blue
  electricity: '#f59e0b', // amber
  management: '#8b5cf6', // purple
  tax: '#ef4444',       // red
  Debt: '#64748b',      // slate
  Equity: '#10b981',    // emerald
}

export function colorForCategory(category: string, index: number = 0): string {
  const FALLBACK = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']
  return CATEGORY_COLORS[category] ?? FALLBACK[index % FALLBACK.length]
}
