// frontend/src/components/forms/VacateTenantForm.tsx
//
// Small form for the `POST /api/v1/tenants/<id>/vacate/` action — it
// captures the new `lease_end` date and submits it. The tenant id is
// supplied by the caller (the page already knows which tenant it is).
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
  lease_end: z.string().min(1, 'Required'),
})
// See PropertyForm for the zod 4 + RHF input/output typing rationale.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  defaultValues?: Partial<Input>
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
}

export function VacateTenantForm({
  defaultValues,
  onSubmit,
  isSubmitting,
}: Props) {
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      lease_end: '',
      ...defaultValues,
    },
  })

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="lease_end"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Lease end</FormLabel>
              <FormControl>
                <Input type="date" {...field} />
              </FormControl>
              <FormDescription>
                The tenant will be marked as vacated as of this date.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" variant="destructive" disabled={isSubmitting}>
          Vacate tenant
        </Button>
      </form>
    </Form>
  )
}
