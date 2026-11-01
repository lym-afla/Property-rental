import { useEffect, useRef, useState } from 'react'
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
import { TRANSACTION_CATEGORIES } from '@/lib/transactionCategories'
import { tenantStatus } from '@/lib/tenantStatus'
import { CURRENCY_OPTIONS } from './PropertyForm'

export const TRANSACTION_CATEGORY_OPTIONS = TRANSACTION_CATEGORIES.map(
  ({ value }) => value,
) as [
  (typeof TRANSACTION_CATEGORIES)[number]['value'],
  ...(typeof TRANSACTION_CATEGORIES)[number]['value'][],
]

// Zod regex for the optional "YYYY-MM" period string. The field is
// optional (the backend column is nullable), but when present it must
// match the YYYY-MM shape the rest of the app relies on.
const PERIOD_REGEX = /^\d{4}-(0[1-9]|1[0-2])$/

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
  // Optional, auto-derived from `date` but user-editable. The
  // `.or(literal(''))` lets the field render empty (no period set) and
  // the `.optional()` lets it be omitted entirely.
  period: z
    .string()
    .regex(PERIOD_REGEX, 'Format must be YYYY-MM (e.g. 2026-03)')
    .or(z.literal(''))
    .optional(),
  comment: z.string().optional().default(''),
})
// See PropertyForm for the zod 4 + RHF input/output typing rationale.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  mode?: 'create' | 'edit'
  properties: Property[]
  tenants: Tenant[]
  defaultValues?: Partial<Input>
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
}

// Extract the YYYY-MM substring from an ISO date. Returns '' for invalid
// input so the caller can safely `setValue('period', derived)` even
// before the user has typed a full date.
function derivePeriod(dateStr: string | undefined | null): string {
  if (!dateStr) return ''
  // Accept both `YYYY-MM-DD` and `YYYY-MM`. Slicing the first 7 chars
  // gives us the `YYYY-MM` prefix either way; we then validate the
  // month is 01-12 to avoid deriving nonsense from a half-typed date.
  const prefix = dateStr.slice(0, 7)
  return PERIOD_REGEX.test(prefix) ? prefix : ''
}

export function TransactionForm({
  mode = 'create',
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
      currency: (properties.find((property) => property.id === Number(defaultValues?.property))?.currency ?? 'USD') as Output['currency'],
      period: derivePeriod(defaultValues?.date),
      comment: '',
      ...defaultValues,
    },
  })

  const selectedProperty = useWatch({ control: form.control, name: 'property' })
  const initializedCurrency = useRef(mode === 'edit')
  const [showFormerOverride, setShowFormerOverride] = useState<boolean | null>(null)
  const assignedTenant = tenants.find((tenant) => tenant.id === Number(defaultValues?.tenant))
  const showFormer = showFormerOverride ?? (mode === 'edit' && tenantStatus(assignedTenant?.lease_end) === 'vacated')

  useEffect(() => {
    if (initializedCurrency.current) return
    const property = properties.find((item) => item.id === Number(selectedProperty))
    if (!property) return
    if (!form.getFieldState('currency').isDirty) {
      form.setValue('currency', property.currency as Output['currency'])
    }
    initializedCurrency.current = true
  }, [selectedProperty, properties, form])

  const filteredTenants = tenants
    .filter((tenant) => tenant.property === Number(selectedProperty)
      && (showFormer || tenantStatus(tenant.lease_end) !== 'vacated'))
    .sort((a, b) => Number(tenantStatus(a.lease_end) === 'vacated') - Number(tenantStatus(b.lease_end) === 'vacated'))

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
                  <Input type="date" {...field} onChange={(event) => {
                    field.onChange(event)
                    form.setValue('period', derivePeriod(event.target.value), { shouldDirty: true })
                  }} />
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
                    if (num !== Number(field.value)) {
                      const property = properties.find((item) => item.id === num)
                      if (property) {
                        form.setValue('currency', property.currency as Output['currency'], { shouldDirty: true })
                        initializedCurrency.current = true
                      }
                    }
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
                      form.setValue('tenant', null, { shouldDirty: true })
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
                disabled={!selectedProperty}
                onValueChange={(v) => field.onChange(v === '__unassigned__' ? null : Number(v))}
                value={
                  field.value !== null && field.value !== undefined
                    ? String(field.value)
                    : '__unassigned__'
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
                  <SelectItem value="__unassigned__">Unassigned</SelectItem>
                  {filteredTenants.length === 0 ? (
                    <SelectItem value="__none__" disabled>
                      {showFormer ? 'No tenants for this property' : 'No current tenants for this property'}
                    </SelectItem>
                  ) : (
                    filteredTenants.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.first_name} {t.last_name}{tenantStatus(t.lease_end) === 'vacated' ? ' · Former tenant' : ''}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showFormer}
            onChange={(event) => {
              const checked = event.target.checked
              setShowFormerOverride(checked)
              const tenant = tenants.find((item) => item.id === Number(form.getValues('tenant')))
              if (!checked && tenantStatus(tenant?.lease_end) === 'vacated') {
                form.setValue('tenant', null, { shouldDirty: true })
              }
            }}
          />
          Show former tenants
        </label>

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
                    {TRANSACTION_CATEGORIES.map(({ value, label }) => (
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
            name="currency"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Currency</FormLabel>
                <Select onValueChange={(value) => {
                  if (value) field.onChange(value)
                }} value={field.value}>
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
            name="period"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Period</FormLabel>
                <FormControl>
                  <Input
                    type="month"
                    {...field}
                    value={field.value || ''}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

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
