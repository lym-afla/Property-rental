// frontend/src/components/forms/PropertyValuationForm.tsx
//
// Form for creating/editing a PropertyCapitalStructure row (backing
// the `/api/v1/property-valuations/` endpoint). Field names mirror
// `PropertyCapitalStructureSerializer`.
//
// `property` is typically set from the route/page context rather than
// user input, so it's not part of the form (callers pass it in via
// `onSubmit` or include it in `defaultValues` if they want the form
// to capture it).
import type { Loan } from '@/types/loan'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

const schema = z.object({
  loan: z.number().int().positive().nullable().optional(),
  capital_structure_date: z.string().min(1, 'Required'),
  capital_structure_value: z.string().trim().nullable(),
  capital_structure_debt: z.string().nullable().optional().default(''),
}).superRefine((values, ctx) => {
  if (!values.capital_structure_value && !values.capital_structure_debt?.trim()) {
    ctx.addIssue({ code: 'custom', path: ['capital_structure_value'], message: 'Enter a total value or a debt balance' })
  }
  if (Number(values.capital_structure_debt || 0) !== 0 && !values.loan) ctx.addIssue({ code: 'custom', path: ['loan'], message: 'Select a loan for a non-zero debt balance' })
}).transform((values) => ({
  ...values,
  capital_structure_value: values.capital_structure_value || null,
  capital_structure_debt: values.capital_structure_debt?.trim() || null,
}))
// See PropertyForm for the zod 4 + RHF input/output typing rationale.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  loans?: Loan[]
  defaultValues?: Partial<Input>
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
}

export function PropertyValuationForm({
  loans = [],
  defaultValues,
  onSubmit,
  isSubmitting,
}: Props) {
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      capital_structure_date: '',
      capital_structure_value: '',
      capital_structure_debt: '',
      ...defaultValues,
    },
  })

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="capital_structure_date"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Date</FormLabel>
              <FormControl>
                <Input className="min-h-11" type="date" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="capital_structure_value"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Total value</FormLabel>
              <FormControl>
                <Input
                  type="text"
                  className="min-h-11"
                  inputMode="decimal"
                  placeholder="e.g. 250000.00"
                  {...field}
                  value={field.value ?? ''}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="capital_structure_debt"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Debt</FormLabel>
              <FormControl>
                <Input
                  type="text"
                  className="min-h-11"
                  inputMode="decimal"
                  placeholder="e.g. 100000.00"
                  {...field}
                  value={field.value ?? ''}
                />
              </FormControl>
              <FormDescription>Leave blank for no debt observation; enter 0 to record a payoff.</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField control={form.control} name="loan" render={({ field }) => <FormItem>
          <FormLabel>Loan for debt balance</FormLabel>
          <FormControl><select className="min-h-11 w-full rounded-md border bg-background px-3" value={field.value ?? ''} onChange={(event) => field.onChange(event.target.value ? Number(event.target.value) : null)}>
            <option value="">No loan</option>{loans.map((loan) => <option key={loan.id} value={loan.id}>{loan.lender}{loan.reference ? ` · ${loan.reference}` : ''}</option>)}
          </select></FormControl><FormMessage />
        </FormItem>} />

        <Button className="min-h-11" type="submit" disabled={isSubmitting}>
          Save
        </Button>
      </form>
    </Form>
  )
}
