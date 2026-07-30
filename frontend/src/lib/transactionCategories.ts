export const TRANSACTION_CATEGORIES = [
  { value: 'rent', label: 'Rent' },
  { value: 'tax', label: 'Tax' },
  { value: 'capex', label: 'Capex' },
  { value: 'management', label: 'Management' },
  { value: 'electricity', label: 'Electricity' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'internet', label: 'Internet' },
  { value: 'cost_reimbursement', label: 'Cost reimbursement' },
  { value: 'other_expenses', label: 'Other expenses' },
] as const

export function transactionCategoryLabel(key: string): string {
  return TRANSACTION_CATEGORIES.find(({ value }) => value === key)?.label
    ?? key.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
}
