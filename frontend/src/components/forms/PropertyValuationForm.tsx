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
  capital_structure_date: z.string().min(1, 'Required'),
  capital_structure_value: z.string().min(1, 'Required'),
  capital_structure_debt: z.string().optional().default(''),
}).transform((values) => ({
  ...values,
  capital_structure_debt: values.capital_structure_debt?.trim() || '0',
}))
// See PropertyForm for the zod 4 + RHF input/output typing rationale.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  defaultValues?: Partial<Input>
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
}

export function PropertyValuationForm({
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
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button className="min-h-11" type="submit" disabled={isSubmitting}>
          Save
        </Button>
      </form>
    </Form>
  )
}
