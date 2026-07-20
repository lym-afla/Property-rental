// frontend/src/components/forms/TransactionForm.tsx
//
// Form for creating/editing a Transaction. The tenant Select cascades:
// `useWatch` tracks the selected `property`, and the tenant list is
// filtered to those whose `property` matches. When the property
// changes, the previously-selected tenant is cleared if it no longer
// belongs to the new property.
//
// `category` mirrors `TRANSACTION_CATEGORIES` and `currency` mirrors
// `CURRENCY_CHOICES` from `rentals/constants.py`.
//
// Field names mirror `TransactionSerializer` (`rentals/api/serializers.py`).
import { useForm, useWatch } from 'react-hook-form'
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
import type { Property } from '@/types/property'
import type { Tenant } from '@/types/tenant'
import { CURRENCY_OPTIONS } from './PropertyForm'

// Categories mirror `rentals/constants.py::TRANSACTION_CATEGORIES`.
export const TRANSACTION_CATEGORY_OPTIONS = [
  'rent',
  'tax',
  'capex',
  'management',
  'electricity',
  'utilities',
  'internet',
  'other_income',
  'other_expenses',
] as const

const schema = z.object({
  date: z.string().min(1, 'Required'),
  property: z.coerce
    .number({ message: 'Required' })
    .int()
    .min(1, 'Required'),
  tenant: z.coerce.number().int().min(1).nullable().optional(),
  category: z.enum(TRANSACTION_CATEGORY_OPTIONS),
  amount: z.string().min(1, 'Required'),
  currency: z.enum(CURRENCY_OPTIONS),
  comment: z.string().optional().default(''),
})
// See PropertyForm for the zod 4 + RHF input/output typing rationale.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  properties: Property[]
  tenants: Tenant[]
  defaultValues?: Partial<Input>
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
}

export function TransactionForm({
  properties,
  tenants,
  defaultValues,
  onSubmit,
  isSubmitting,
}: Props) {
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      date: '',
      property: undefined,
      tenant: null,
      category: 'rent',
      amount: '',
      currency: 'USD',
      comment: '',
      ...defaultValues,
    },
  })

  // Cascade: watch the selected property and narrow the tenant list.
  // If the selected property changes and the previously-selected tenant
  // no longer belongs to it, clear the tenant field so we never submit
  // a property/tenant mismatch.
  const selectedProperty = useWatch({
    control: form.control,
    name: 'property',
  })

  const filteredTenants =
    selectedProperty !== undefined && selectedProperty !== null
      ? tenants.filter((t) => t.property === Number(selectedProperty))
      : tenants

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Date</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="property"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Property</FormLabel>
                <Select
                  onValueChange={(v) => {
                    const num = Number(v)
                    field.onChange(num)
                    // Clear the tenant if it doesn't belong to the new property.
                    const currentTenant = form.getValues('tenant')
                    if (
                      currentTenant !== null &&
                      currentTenant !== undefined &&
                      !tenants.some(
                        (t) =>
                          t.id === Number(currentTenant) &&
                          t.property === num,
                      )
                    ) {
                      form.setValue('tenant', null)
                    }
                  }}
                  value={field.value !== undefined ? String(field.value) : undefined}
                >
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select property" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {properties.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="tenant"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Tenant (optional)</FormLabel>
              <Select
                onValueChange={(v) => field.onChange(Number(v))}
                value={
                  field.value !== null && field.value !== undefined
                    ? String(field.value)
                    : undefined
                }
              >
                <FormControl>
                  <SelectTrigger className="w-full">
                    <SelectValue
                      placeholder={
                        selectedProperty
                          ? 'Select tenant'
                          : 'Select a property first'
                      }
                    />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {filteredTenants.length === 0 ? (
                    <SelectItem value="__none__" disabled>
                      No tenants for this property
                    </SelectItem>
                  ) : (
                    filteredTenants.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.first_name} {t.last_name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="category"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Category</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {TRANSACTION_CATEGORY_OPTIONS.map((c) => (
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
        </div>

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
                  placeholder="e.g. 800.00 or -150.00"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="comment"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Comment</FormLabel>
              <FormControl>
                <Input {...field} value={field.value ?? ''} />
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
