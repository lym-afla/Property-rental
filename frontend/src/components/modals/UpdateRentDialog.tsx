// frontend/src/components/modals/UpdateRentDialog.tsx
//
// Specialized dialog for the `POST /api/v1/lease-rents/` action (see
// `LeaseRentViewSet` in `rentals/api/views.py`). Wraps `LeaseRentForm`
// in a shadcn Dialog and wires the `useCreateLeaseRent` mutation hook:
//   - on submit: POST `{ tenant, date_rent_set, rent, currency }` to
//     create a new effective-date rent entry on the tenant's history,
//   - on success: toast, run `onSuccess` (page closes the dialog). The
//     mutation hook also invalidates `tenants.all` so the cached
//     `with_stats` row (which exposes the aggregated `rent_rate`)
//     refetches with the new rate.
//   - on error: toast the surfaced error message.
//
// `tenantId` + `currency` are supplied by the caller (the page already
// knows which tenant row was clicked and what its property currency is).
// The dialog is fully controlled.
import { toast } from 'sonner'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { LeaseRentForm } from '@/components/forms/LeaseRentForm'
import { useCreateLeaseRent } from '@/api/leaseRents'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  tenantId: number | null
  /** Tenant's property currency — auto-filled into the form's
   * `currency` field (read-only). */
  currency: string
  /** Optional seed for the rent amount (e.g. the current rate as a
   * string). */
  defaultRent?: string
  tenantLabel?: string
  /** Fired after a successful create — the page typically closes the
   * dialog. */
  onSuccess?: () => void
}

export function UpdateRentDialog({
  open,
  onOpenChange,
  tenantId,
  currency,
  defaultRent,
  tenantLabel,
  onSuccess,
}: Props) {
  const createLeaseRent = useCreateLeaseRent()

  const handleSubmit = (values: {
    date_rent_set: string
    rent: string
    currency: string
  }) => {
    if (tenantId == null) return
    createLeaseRent.mutate(
      {
        tenant: tenantId,
        date_rent_set: values.date_rent_set,
        rent: values.rent,
        currency: values.currency,
      },
      {
        onSuccess: () => {
          toast.success('Rent rate updated')
          onSuccess?.()
        },
        onError: (err: unknown) => {
          const msg =
            err instanceof Error ? err.message : 'Failed to update rent rate'
          toast.error(msg)
        },
      },
    )
  }

  const title = tenantLabel
    ? `Update rent rate for ${tenantLabel}`
    : 'Update rent rate'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Set a new monthly rent rate effective from the chosen date. A new
            entry is appended to the tenant's rent history; the current rate
            is the latest entry dated on or before today.
          </DialogDescription>
        </DialogHeader>
        <LeaseRentForm
          currency={currency}
          defaultRent={defaultRent}
          onSubmit={handleSubmit}
          isSubmitting={createLeaseRent.isPending}
        />
      </DialogContent>
    </Dialog>
  )
}
