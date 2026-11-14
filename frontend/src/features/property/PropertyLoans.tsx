import { apiErrorMessage } from '@/api/client'
import { useState } from 'react'
import { toast } from 'sonner'
import { useLoanPayment, useLoanReconciliation, useLoans, useSaveLoan } from '@/api/loans'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { LoanPaymentForm } from '@/components/forms/LoanPaymentForm'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ErrorState } from '@/components/states/ErrorState'
import { formatAccounting, formatDate } from '@/lib/format'
import type { Loan } from '@/types/loan'

export function PropertyLoans({ property, currency }: { property: number; currency: string }) {
  const loans = useLoans(property)
  const save = useSaveLoan()
  const payment = useLoanPayment()
  const [editing, setEditing] = useState<Partial<Loan> | null>(null)
  const [paying, setPaying] = useState<Loan | null>(null)
  return <div className="space-y-4">
    <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Loans</h2><Button onClick={() => setEditing({ property, currency })}>Add loan</Button></div>
    {loans.isLoading ? <p>Loading loans…</p> : loans.isError ? <ErrorState message="Failed to load loans" onRetry={() => loans.refetch()} /> : !loans.data?.length ? <p className="text-muted-foreground">No loans recorded yet.</p> : loans.data.map((loan) => <div key={loan.id} className="space-y-3 rounded-md border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold">{loan.lender}</h3><p className="text-sm text-muted-foreground">{loan.reference} · {loan.currency} · From {formatDate(loan.start_date)}{loan.end_date ? ` to ${formatDate(loan.end_date)}` : ''}</p></div><div className="flex gap-2"><Button variant="outline" onClick={() => setEditing(loan)}>Edit loan</Button><Button onClick={() => setPaying(loan)}>Record payment</Button></div></div>
      {loan.lender.startsWith('UNKNOWN') && <p role="alert" className="text-amber-700">Fill in the lender for this migrated loan.</p>}
      <Reconciliation loan={loan} />
    </div>)}
    {editing && <EntityFormDialog open onOpenChange={(open) => { if (!open) setEditing(null) }} title="Loan" mode={editing.id ? 'edit' : 'create'}>
      <form className="space-y-3" onSubmit={(event) => {
        event.preventDefault()
        const fields = new FormData(event.currentTarget)
        const text = (key: string) => String(fields.get(key) ?? '').trim()
        save.mutate({ ...editing, property, currency, lender: text('lender'), reference: text('reference'), start_date: text('start_date'), end_date: text('end_date') || null, original_principal: text('original_principal') || null, interest_rate: text('interest_rate') || null, rate_type: text('rate_type') as Loan['rate_type'] }, { onSuccess: () => { setEditing(null); toast.success('Loan saved') }, onError: (error) => toast.error(apiErrorMessage(error, 'Failed to save loan')) })
      }}>
        <p className="text-sm text-muted-foreground">Currency: {currency}</p>
        <label className="block">Lender<Input name="lender" required defaultValue={editing.lender} /></label>
        <label className="block">Reference (optional)<Input name="reference" defaultValue={editing.reference} /></label>
        <label className="block">Start date<Input name="start_date" type="date" required defaultValue={editing.start_date} /></label>
        <label className="block">End date (optional)<Input name="end_date" type="date" defaultValue={editing.end_date ?? ''} /></label>
        <label className="block">Original principal (optional)<Input name="original_principal" type="number" min="0" step="0.01" defaultValue={editing.original_principal ?? ''} /></label>
        <label className="block">Interest rate % (optional)<Input name="interest_rate" type="number" min="0" step="0.0001" defaultValue={editing.interest_rate ?? ''} /></label>
        <label className="block">Rate type<select name="rate_type" defaultValue={editing.rate_type ?? ''} className="block min-h-11 w-full rounded-md border bg-background px-3"><option value="">Unspecified</option><option value="fixed">Fixed</option><option value="variable">Variable</option></select></label>
        <Button disabled={save.isPending} type="submit">Save loan</Button>
      </form>
    </EntityFormDialog>}
    {paying && <EntityFormDialog open onOpenChange={(open) => { if (!open) setPaying(null) }} title="Mortgage payment" mode="create" description={`${paying.lender} · ${currency}`}>
      <LoanPaymentForm isSubmitting={payment.isPending} onSubmit={(data) => payment.mutate({ id: paying.id, data }, { onSuccess: () => { setPaying(null); toast.success('Interest and principal recorded') }, onError: (error) => toast.error(apiErrorMessage(error, 'Failed to record payment')) })} />
    </EntityFormDialog>}
  </div>
}

function Reconciliation({ loan }: { loan: Loan }) {
  const query = useLoanReconciliation(loan.id)
  if (query.isError) return <ErrorState message="Failed to check loan balances" onRetry={() => query.refetch()} />
  if (query.isLoading) return <p className="text-sm">Checking balances…</p>
  const rows = query.data ?? []
  if (!rows.length) return <p className="text-sm text-muted-foreground">Record two dated debt balances to check principal repayments.</p>
  const flagged = rows.filter((row) => row.flagged)
  return flagged.length ? <div role="alert" className="space-y-1 text-sm text-amber-700">{flagged.map((row) => <p key={`${row.opening_date}-${row.closing_date}`}>Balance mismatch {formatDate(row.opening_date)} – {formatDate(row.closing_date)}: expected {formatAccounting(row.expected_closing_debt, loan.currency)}, recorded {formatAccounting(row.closing_debt, loan.currency)} (difference {formatAccounting(row.difference, loan.currency)}). Review debt balances and principal payments.</p>)}</div> : <p className="text-sm text-muted-foreground">Recorded debt balances agree with principal payments within 1 {loan.currency}.</p>
}
