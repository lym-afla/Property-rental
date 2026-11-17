import { useState } from 'react'
import { toast } from 'sonner'
import { apiErrorMessage } from '@/api/client'
import { useDeleteLoanProduct, useLoanProducts, useSaveLoanProduct } from '@/api/loans'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatAccounting, formatDate } from '@/lib/format'
import type { Loan, LoanProduct, LoanProductInput } from '@/types/loan'

export function LoanProducts({ loan }: { loan: Loan }) {
  const products = useLoanProducts(loan.id)
  const save = useSaveLoanProduct()
  const remove = useDeleteLoanProduct()
  const [editing, setEditing] = useState<LoanProductInput | null>(null)
  const [deleting, setDeleting] = useState<LoanProduct | null>(null)
  const rows = [...(products.data ?? [])].sort((a, b) => a.start_date.localeCompare(b.start_date) || a.id - b.id)
  return <section className="space-y-3" aria-label={`Mortgage products for ${loan.lender}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="font-medium">Mortgage products</h4>
      <Button variant="outline" onClick={() => setEditing({ loan: loan.id, name: '', lender: loan.lender, start_date: '', end_date: null, interest_rate: null, rate_type: '', opening_balance: null, notes: '' })}>Add mortgage product</Button>
    </div>
    <p className="text-sm text-muted-foreground">Record each product or standard-rate period separately. Payments and balance checks stay together on this loan.</p>
    {products.isLoading ? <p className="text-sm">Loading mortgage products…</p> : products.isError ? <ErrorState message="Failed to load mortgage products" onRetry={() => products.refetch()} /> : !rows.length ? <p className="text-sm text-muted-foreground">No mortgage products recorded.</p> : <ol className="space-y-3">{rows.map((product) => <li key={product.id} className="space-y-1 rounded-md border p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><h5 className="font-medium">{product.name}</h5><p>{product.lender}</p></div>
        <div className="flex gap-2"><Button size="sm" variant="outline" className="min-h-11" onClick={() => setEditing(product)}>Edit product</Button><Button size="sm" variant="outline" className="min-h-11" onClick={() => setDeleting(product)}>Delete product</Button></div>
      </div>
      <p>{formatDate(product.start_date)} – {product.end_date ? formatDate(product.end_date) : 'Ongoing'}</p>
      <p>{product.interest_rate === null ? 'Initial rate unknown' : `Initial rate: ${Number(product.interest_rate)}% ${product.rate_type || '(type unknown)'}`}</p>
      {product.opening_balance !== null && <p>Opening balance: {formatAccounting(product.opening_balance, loan.currency)}</p>}
      {product.notes && <p className="whitespace-pre-wrap text-muted-foreground">{product.notes}</p>}
    </li>)}</ol>}
    {editing && <EntityFormDialog open onOpenChange={(open) => { if (!open) setEditing(null) }} title="mortgage product" mode={editing.id ? 'edit' : 'create'} description="Product terms for this existing loan. Saving does not record a payment or change a debt balance.">
      <form className="max-h-[65vh] space-y-3 overflow-y-auto" onSubmit={(event) => {
        event.preventDefault()
        const fields = new FormData(event.currentTarget)
        const text = (key: string) => String(fields.get(key) ?? '').trim()
        save.mutate({ id: editing.id, loan: loan.id, name: text('name'), lender: text('lender'), start_date: text('start_date'), end_date: text('end_date') || null, interest_rate: text('interest_rate') || null, rate_type: text('rate_type') as LoanProduct['rate_type'], opening_balance: text('opening_balance') || null, notes: text('notes') }, {
          onSuccess: () => { setEditing(null); toast.success('Mortgage product saved') },
          onError: (error) => toast.error(apiErrorMessage(error, 'Failed to save mortgage product')),
        })
      }}>
        <p className="text-sm text-muted-foreground">Currency: {loan.currency}</p>
        <label className="block">Product name<Input name="name" required maxLength={200} defaultValue={editing.name} /></label>
        <label className="block">Lender<Input name="lender" required maxLength={200} defaultValue={editing.lender} /></label>
        <label className="block">Start date<Input name="start_date" type="date" required defaultValue={editing.start_date} /></label>
        <label className="block">End date (optional)<Input name="end_date" type="date" defaultValue={editing.end_date ?? ''} /></label>
        <label className="block">Initial interest rate % (optional)<Input name="interest_rate" type="number" min="0" step="0.0001" defaultValue={editing.interest_rate ?? ''} /></label>
        <label className="block">Rate type<select name="rate_type" defaultValue={editing.rate_type} className="block min-h-11 w-full rounded-md border bg-background px-3"><option value="">Unknown</option><option value="fixed">Fixed</option><option value="variable">Variable</option></select></label>
        <label className="block">Opening balance (optional)<Input name="opening_balance" type="number" min="0" step="0.01" defaultValue={editing.opening_balance ?? ''} /></label>
        <label className="block">Source and uncertainty notes (optional)<textarea name="notes" maxLength={2000} defaultValue={editing.notes} className="block min-h-24 w-full rounded-md border bg-background p-3" /></label>
        <Button type="submit" disabled={save.isPending}>Save product</Button>
      </form>
    </EntityFormDialog>}
    {deleting && <ConfirmDialog open onOpenChange={(open) => { if (!open) setDeleting(null) }} title="Delete mortgage product?" description="This removes the product terms only. Payments, fees and recorded balances are kept." confirmText="Confirm delete product" confirmVariant="destructive" isLoading={remove.isPending} onConfirm={() => remove.mutate(deleting.id, {
      onSuccess: () => { setDeleting(null); toast.success('Mortgage product deleted') },
      onError: (error) => toast.error(apiErrorMessage(error, 'Failed to delete mortgage product')),
    })} />}
  </section>
}
