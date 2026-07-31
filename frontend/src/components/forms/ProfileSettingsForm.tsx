// frontend/src/components/forms/ProfileSettingsForm.tsx
//
// Form for the `/api/v1/auth/me/` PATCH endpoint — captures the
// user's profile-level settings. Field names mirror the Django `User`
// model in `rentals/models.py` (snake_case preserved on purpose).
//
// NOTE: the model field is `use_default_currency_for_all_data`, not
// `default_currency_for_all_data` as the task brief briefly said — the
// latter would fail the TypeScript build against the `User` type. The
// `defaultValues` here mirror `fixtureUser` so callers can pass an
// existing `User` straight through.
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
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { CURRENCY_OPTIONS } from './PropertyForm'

// Frequency choices mirror `rentals/forms.py::FREQUENCY_CHOICES`.
const FREQUENCY_OPTIONS = ['M', 'Q', 'Y'] as const
// Timeline choices mirror `rentals/forms.py::TIMELINE_CHOICES`.
const TIMELINE_OPTIONS = [
  'YTD',
  '3m',
  '6m',
  '12m',
  '3Y',
  '5Y',
  'All',
  'Custom',
] as const

const FREQUENCY_LABELS: Record<(typeof FREQUENCY_OPTIONS)[number], string> = {
  M: 'Monthly',
  Q: 'Quarterly',
  Y: 'Yearly',
}
const TIMELINE_LABELS: Record<(typeof TIMELINE_OPTIONS)[number], string> = {
  YTD: 'Year to Date',
  '3m': 'Last 3 months',
  '6m': 'Last 6 months',
  '12m': 'Last 12 months',
  '3Y': 'Last 3 years',
  '5Y': 'Last 5 years',
  All: 'All history',
  Custom: 'Custom',
}

const schema = z.object({
  default_currency: z.enum(CURRENCY_OPTIONS),
  use_default_currency_for_all_data: z.boolean(),
  chart_frequency: z.enum(FREQUENCY_OPTIONS),
  chart_timeline: z.enum(TIMELINE_OPTIONS),
  digits: z.coerce
    .number({ message: 'Required' })
    .int()
    .min(0, 'Must be 0 or more')
    .max(6, 'Must be 6 or less'),
  effective_date: z.string().nullable().optional(),
})
// See PropertyForm for the zod 4 + RHF input/output typing rationale.
type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

type Props = {
  defaultValues?: Partial<Input>
  onSubmit: (values: Output) => void
  isSubmitting?: boolean
  showEffectiveDate?: boolean
}

export function ProfileSettingsForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  showEffectiveDate = true,
}: Props) {
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      default_currency: 'USD',
      use_default_currency_for_all_data: false,
      chart_frequency: 'M',
      chart_timeline: '6m',
      digits: 0,
      effective_date: null,
      ...defaultValues,
    },
  })

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="default_currency"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Default currency</FormLabel>
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
            name="digits"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Digits for tables</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    min={0}
                    max={6}
                    step={1}
                    value={(field.value as number | undefined) ?? 0}
                    onChange={(e) => field.onChange(e.target.value)}
                    onBlur={field.onBlur}
                    name={field.name}
                    ref={field.ref}
                  />
                </FormControl>
                <FormDescription>
                  Decimal places shown in tables (0-6).
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="use_default_currency_for_all_data"
          render={({ field }) => (
            <FormItem className="flex flex-row items-start gap-3 space-y-0">
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
              <div className="space-y-1 leading-none">
                <FormLabel>Use default currency for all data</FormLabel>
                <FormDescription>
                  Convert every currency in the app to the default currency
                  for display.
                </FormDescription>
              </div>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="chart_frequency"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Chart frequency</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select frequency" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {FREQUENCY_OPTIONS.map((f) => (
                      <SelectItem key={f} value={f}>
                        {FREQUENCY_LABELS[f]}
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
            name="chart_timeline"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Chart timeline</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select timeline" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {TIMELINE_OPTIONS.map((t) => (
                      <SelectItem key={t} value={t}>
                        {TIMELINE_LABELS[t]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {showEffectiveDate && <FormField
          control={form.control}
          name="effective_date"
          render={({ field }) => (
            <FormItem>
              <FormLabel>As-of date (effective date)</FormLabel>
              <FormControl>
                <Input
                  type="date"
                  value={field.value ?? ''}
                  onChange={(e) =>
                    field.onChange(e.target.value || null)
                  }
                />
              </FormControl>
              <FormDescription>
                The date used for all financial calculations. Leave blank to
                always use today.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />}

        <Button type="submit" disabled={isSubmitting}>
          Save
        </Button>
      </form>
    </Form>
  )
}
