// frontend/src/components/forms/LeaseRentForm.tsx
//
// Form for creating a new `Lease_rent` entry (backing the
// `/api/v1/lease-rents/` endpoint). Used by the tenant detail page's
// "Update rent" dialog to push a new effective-date rent rate.
//
// Field names mirror `LeaseRentSerializer`:
//   - `date_rent_set` — the effective date the new rent applies from
//   - `rent` — the rent amount (decimal)
//   - `currency` — auto-filled from the tenant's property currency; the
//     field is shown read-only because cross-currency rent entries would
//     confuse the per-tenant revenue aggregation (which assumes a single
//     currency per tenant).
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

const schema = z.object({
  date_rent_set: z.string().min(1, 'Required'),
  rent: z.string().min(1, 'Required'),
  currency: z.string().min(1, 'Required'),
})
// See PropertyForm for the zod 4 + RHF input/output typing rationale.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  /** Tenant's property currency — auto-filled into the `currency` field
   * and rendered read-only so the user can't pick a currency that
   * doesn't match the property. */
  currency: string
  /** Optional seed for the rent amount (e.g. the current rate). */
  defaultRent?: string
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
}

export function LeaseRentForm({
  currency,
  defaultRent,
  onSubmit,
  isSubmitting,
}: Props) {
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      // Default effective date = today (the dialog is for "set the new
      // rate that applies from now").
      date_rent_set: new Date().toISOString().slice(0, 10),
      rent: defaultRent ?? '',
      currency: currency || 'USD',
    },
  })

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="date_rent_set"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Effective date</FormLabel>
              <FormControl>
                <Input type="date" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="rent"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Rent amount</FormLabel>
              <FormControl>
                <Input
                  type="text"
                  inputMode="decimal"
                  placeholder="e.g. 1200.00"
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
              <FormControl>
                {/* Read-only: the rent currency must match the tenant's
                    property currency so per-tenant revenue aggregation
                    (which assumes a uniform currency) stays consistent. */}
                <Input {...field} readOnly />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={isSubmitting}>
          Save
        </Button>
      </form>
    </Form>
  )
}
