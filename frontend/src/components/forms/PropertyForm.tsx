// frontend/src/components/forms/PropertyForm.tsx
//
// Form for creating/editing a Property. Field names mirror
// `PropertySerializer` in `rentals/api/serializers.py` (snake_case on
// purpose). Currencies match the backend `CURRENCY_CHOICES` tuple
// (`USD`, `EUR`, `GBP`, `RUB`) — see `rentals/constants.py`.
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'

// Currency choices mirror `rentals/constants.py::CURRENCY_CHOICES`.
export const CURRENCY_OPTIONS = ['USD', 'EUR', 'GBP', 'RUB'] as const

const schema = z.object({
  name: z.string().min(1, 'Required'),
  location: z.string().min(1, 'Required'),
  address: z.string().optional().default(''),
  num_bedrooms: z.coerce.number().int().min(0, 'Must be 0 or more'),
  area: z.string().optional().default(''),
  currency: z.enum(CURRENCY_OPTIONS),
  sold: z.string().nullable().optional(),
})
// In zod 4 + react-hook-form 7, `z.coerce.number()` infers an input type
// of `unknown` (form fields hold strings) and an output type of `number`.
// We type `useForm<Input, Context, Output>` so handleSubmit yields the
// validated output shape; the input shape is what the fields see.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  defaultValues?: Partial<Input>
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
}

export function PropertyForm({ defaultValues, onSubmit, isSubmitting }: Props) {
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      location: '',
      address: '',
      num_bedrooms: 0,
      area: '',
      currency: 'USD',
      sold: null,
      ...defaultValues,
    },
  })

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="location"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Location</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="address"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Address</FormLabel>
              <FormControl>
                <Input {...field} value={field.value ?? ''} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="num_bedrooms"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Bedrooms</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  min={0}
                  step={1}
                  value={(field.value as number | undefined) ?? 0}
                  onChange={(e) => field.onChange(e.target.value)}
                  onBlur={field.onBlur}
                  name={field.name}
                  ref={field.ref}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="area"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Area</FormLabel>
              <FormControl>
                <Input {...field} value={field.value ?? ''} />
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
              <Select onValueChange={field.onChange} value={field.value}>
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

        <FormField
          control={form.control}
          name="sold"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Sold (optional)</FormLabel>
              <FormControl>
                <Input
                  type="date"
                  value={field.value ?? ''}
                  onChange={(e) =>
                    field.onChange(e.target.value || null)
                  }
                />
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
