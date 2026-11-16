import { useState } from 'react'
import { toast } from 'sonner'
import { apiErrorMessage } from '@/api/client'
import { useDeleteLoanCapitalisedFee, useLoanCapitalisedFees, useSaveLoanCapitalisedFee } from '@/api/loans'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatAccounting, formatDate } from '@/lib/format'
import type { Loan, LoanCapitalisedFee, LoanCapitalisedFeeInput } from '@/types/loan'

export function LoanCapitalisedFees({ loan }: { loan: Loan }) {
  const fees = useLoanCapitalisedFees(loan.id)
  const save = useSaveLoanCapitalisedFee()
  const remove = useDeleteLoanCapitalisedFee()
  const [editing, setEditing] = useState<LoanCapitalisedFeeInput | null>(null)
  const [deleting, setDeleting] = useState<LoanCapitalisedFee | null>(null)
  return <section className="space-y-2" aria-label={`Capitalised fees for ${loan.lender}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="font-medium">Capitalised fees</h4>
      <Button variant="outline" onClick={() => setEditing({ loan: loan.id, date: '', amount: '', description: '' })}>Add capitalised fee</Button>
    </div>
    <p className="text-sm text-muted-foreground">Fees added to the loan balance are included in balance checks. They do not record a cash payment.</p>
    {fees.isLoading ? <p className="text-sm">Loading fees…</p> : fees.isError ? <ErrorState message="Failed to load capitalised fees" onRetry={() => fees.refetch()} /> : !fees.data?.length ? <p className="text-sm text-muted-foreground">No capitalised fees recorded.</p> : <ul className="space-y-2">{fees.data.map((fee) => <li key={fee.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <div>{formatDate(fee.date)} · {formatAccounting(fee.amount, loan.currency)}{fee.description && <span className="ml-2">{fee.description}</span>}</div>
      <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setEditing(fee)}>Edit fee</Button><Button size="sm" variant="outline" onClick={() => setDeleting(fee)}>Delete fee</Button></div>
    </li>)}</ul>}
    {editing && <EntityFormDialog open onOpenChange={(open) => { if (!open) setEditing(null) }} title="capitalised fee" mode={editing.id ? 'edit' : 'create'} description="Added to the loan balance; no cash payment is recorded.">
      <form className="space-y-3" onSubmit={(event) => {
        event.preventDefault()
        const fields = new FormData(event.currentTarget)
        save.mutate({ id: editing.id, loan: loan.id, date: String(fields.get('date')), amount: String(fields.get('amount')), description: String(fields.get('description') ?? '').trim() }, {
          onSuccess: () => { setEditing(null); toast.success('Capitalised fee saved') },
          onError: (error) => toast.error(apiErrorMessage(error, 'Failed to save fee')),
        })
      }}>
        <label className="block">Fee date<Input name="date" type="date" required defaultValue={editing.date} /></label>
        <label className="block">Fee amount<Input name="amount" type="number" min="0.01" step="0.01" required defaultValue={editing.amount} /></label>
        <label className="block">Description (optional)<Input name="description" maxLength={250} defaultValue={editing.description} /></label>
        <Button type="submit" disabled={save.isPending}>Save fee</Button>
      </form>
    </EntityFormDialog>}
    {deleting && <ConfirmDialog open onOpenChange={(open) => { if (!open) setDeleting(null) }} title="Delete capitalised fee?" description="This removes the fee from loan balance checks." confirmText="Confirm delete fee" confirmVariant="destructive" isLoading={remove.isPending} onConfirm={() => remove.mutate(deleting.id, {
      onSuccess: () => { setDeleting(null); toast.success('Capitalised fee deleted') },
      onError: (error) => toast.error(apiErrorMessage(error, 'Failed to delete fee')),
    })} />}
  </section>
}
