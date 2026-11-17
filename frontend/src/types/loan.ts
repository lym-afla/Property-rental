export type Loan = {
  id: number
  property: number
  lender: string
  currency: string
  reference: string
  start_date: string
  end_date: string | null
  original_principal: string | null
  interest_rate: string | null
  rate_type: '' | 'fixed' | 'variable'
  created_at: string
  updated_at: string
}
export type LoanPayment = { date: string; interest: string; total?: string; principal?: string; comment?: string; period?: string }
export type LoanReconciliation = {
  opening_date: string; closing_date: string; opening_debt: string; principal_paid: string
  capitalised_fees?: string; closing_debt: string; expected_closing_debt: string; difference: string; flagged: boolean
}

export type LoanCapitalisedFee = {
  id: number
  loan: number
  property: number
  date: string
  amount: string
  description: string
  created_at: string
  updated_at: string
}
export type LoanCapitalisedFeeInput = Pick<LoanCapitalisedFee, 'loan' | 'date' | 'amount' | 'description'> & { id?: number }

export type LoanProduct = {
  id: number
  loan: number
  name: string
  lender: string
  start_date: string
  end_date: string | null
  interest_rate: string | null
  rate_type: '' | 'fixed' | 'variable'
  opening_balance: string | null
  notes: string
  created_at: string
  updated_at: string
}
export type LoanProductInput = Omit<LoanProduct, 'id' | 'created_at' | 'updated_at'> & { id?: number }
