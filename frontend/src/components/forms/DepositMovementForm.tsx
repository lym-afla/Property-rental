// frontend/src/components/forms/DepositMovementForm.tsx
//
// Create/edit form for a tenant security-deposit movement (backing
// `/api/v1/deposit-movements/`). Field names mirror
// `DepositMovementSerializer`.
//
// - `kind` is Received / Returned / Applied. Only Applied shows "Applies to"
//   and "Transaction"; for the other kinds both are submitted as `null`.
// - `currency` is read-only when the tenant already holds a deposit in a
//   currency (`lockedCurrency`), a select of the supported currencies otherwise.
// - "Transaction" defaults to "Create new transaction" (`transaction: null`)
//   or attaches the movement to one of `candidateTransactions` with matching
//   category and currency that is not linked to another movement. Choosing
//   one copies its date into `date` and disables the date input.
// - Server 400 field errors thrown by `apiFetch` (`ApiError.body`, values
//   either a list of strings or a plain string) are mapped onto the fields.
import { useEffect } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { ApiError } from '@/api/client'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { CURRENCY_OPTIONS } from './PropertyForm'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import type { DepositMovement } from '@/types/deposit'
import type { Transaction } from '@/types/transaction'

export type DepositMovementInput = Omit<DepositMovement, 'id' | 'owns_transaction'>

const KIND_OPTIONS = [
  { value: 'received', label: 'Received' },
  { value: 'returned', label: 'Returned' },
  { value: 'applied', label: 'Applied' },
] as const

const APPLIED_TO_OPTIONS = [
  { value: 'rent', label: 'Rent' },
  { value: 'cost_reimbursement', label: 'Cost reimbursement' },
] as const

const NEW_TRANSACTION = 'new'

const schema = z
  .object({
    date: z.string().min(1, 'Required'),
    kind: z.enum(['received', 'returned', 'applied']),
    amount: z.string().min(1, 'Required'),
    currency: z.string().min(1, 'Required'),
    applied_to: z.enum(['rent', 'cost_reimbursement']).nullable(),
    transaction: z.number().nullable(),
    comment: z.string(),
  })
  .superRefine((v, ctx) => {
    if (v.kind === 'applied' && v.applied_to === null) {
      ctx.addIssue({ code: 'custom', path: ['applied_to'], message: 'Required' })
    }
  })
type FormValues = z.infer<typeof schema>

type Props = {
  tenantId: number
  defaultCurrency: string
  /** Currency of the tenant's existing deposit, or null when none exists. */
  lockedCurrency: string | null
  candidateTransactions: Transaction[]
  initial?: DepositMovement
  onSubmit: (data: DepositMovementInput) => Promise<void>
  onCancel: () => void
}

const FIELD_NAMES = [
  'date',
  'kind',
  'amount',
  'currency',
  'applied_to',
  'transaction',
  'comment',
] as const
type FieldName = (typeof FIELD_NAMES)[number]

function messageOf(value: unknown): string {
  return Array.isArray(value) ? value.join(' ') : String(value)
}

export function DepositMovementForm({
  tenantId,
  defaultCurrency,
  lockedCurrency,
  candidateTransactions,
  initial,
  onSubmit,
  onCancel,
}: Props) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      date: initial?.date ?? '',
      kind: initial?.kind ?? 'received',
      amount: initial?.amount ?? '',
      currency: lockedCurrency ?? initial?.currency ?? defaultCurrency,
      applied_to: initial?.applied_to ?? null,
      transaction: initial?.transaction ?? null,
      comment: initial?.comment ?? '',
    },
  })

  const [kind, appliedTo, currency, transaction] = useWatch({
    control: form.control,
    name: ['kind', 'applied_to', 'currency', 'transaction'],
  })
  const isApplied = kind === 'applied'

  const candidates = candidateTransactions.filter(
    (t) =>
      t.category === appliedTo &&
      t.currency === currency &&
      (t.deposit_movement === null || t.deposit_movement === initial?.id),
  )
  const selected = candidates.find((t) => t.id === transaction)
  // A movement that created its own transaction stays tied to it (the server
  // rejects relinking) but its date remains editable and is synced server-side.
  const ownsTransaction = initial?.owns_transaction === true

  // Drop a selection that stopped being a candidate (category/currency/kind
  // changed) so we never submit a mismatched link.
  useEffect(() => {
    if (!ownsTransaction && transaction !== null && !selected) {
      form.setValue('transaction', null)
    }
  }, [transaction, selected, ownsTransaction, form])

  async function submit(values: FormValues) {
    const applied = values.kind === 'applied'
    const data: DepositMovementInput = {
      tenant: tenantId,
      date: values.date,
      kind: values.kind,
      currency: values.currency,
      amount: values.amount,
      applied_to: applied ? values.applied_to : null,
      transaction: applied ? values.transaction : null,
      comment: values.comment === '' ? null : values.comment,
    }
    try {
      await onSubmit(data)
    } catch (err) {
      if (err instanceof ApiError && err.body && typeof err.body === 'object') {
        const rest: string[] = []
        for (const [key, value] of Object.entries(err.body)) {
          if ((FIELD_NAMES as readonly string[]).includes(key)) {
            form.setError(key as FieldName, { message: messageOf(value) })
          } else {
            rest.push(messageOf(value))
          }
        }
        if (rest.length) form.setError('root', { message: rest.join(' ') })
        return
      }
      form.setError('root', { message: 'Something went wrong. Please try again.' })
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(submit)} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Date</FormLabel>
                <FormControl>
                  <Input
                    type="date"
                    {...field}
                    disabled={isApplied && selected !== undefined && !ownsTransaction}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="kind"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Kind</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {KIND_OPTIONS.map(({ value, label }) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="amount"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Amount</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    inputMode="decimal"
                    placeholder="e.g. 1000.00"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="currency"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Currency</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  value={field.value}
                  disabled={lockedCurrency !== null}
                >
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select currency" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {CURRENCY_OPTIONS.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {isApplied && (
          <>
            <FormField
              control={form.control}
              name="applied_to"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Applies to</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value ?? ''}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select what it applies to" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {APPLIED_TO_OPTIONS.map(({ value, label }) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="transaction"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Transaction</FormLabel>
                  <Select
                    disabled={ownsTransaction}
                    onValueChange={(v) => {
                      if (v === NEW_TRANSACTION) {
                        field.onChange(null)
                        return
                      }
                      const id = Number(v)
                      field.onChange(id)
                      const t = candidates.find((c) => c.id === id)
                      if (t) form.setValue('date', t.date)
                    }}
                    value={
                      field.value !== null ? String(field.value) : NEW_TRANSACTION
                    }
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NEW_TRANSACTION}>
                        Create new transaction
                      </SelectItem>
                      {candidates.map((t) => (
                        <SelectItem key={t.id} value={String(t.id)}>
                          {t.date} · {t.amount} {t.currency}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        )}

        <FormField
          control={form.control}
          name="comment"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Comment</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {form.formState.errors.root && (
          <p role="alert" className="text-sm text-destructive">
            {form.formState.errors.root.message}
          </p>
        )}

        <div className="flex gap-2">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            Save
          </Button>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Form>
  )
}
