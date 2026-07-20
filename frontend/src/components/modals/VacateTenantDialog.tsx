// frontend/src/components/modals/VacateTenantDialog.tsx
//
// Specialized dialog for the `POST /api/v1/tenants/<id>/vacate/` action
// (see `TenantViewSet.vacate` in `rentals/api/views.py`). Wraps
// `VacateTenantForm` in a shadcn Dialog and wires the `useVacateTenant`
// mutation hook:
//   - on submit: fire the mutation with `{ id, leaseEnd }`,
//   - on success: toast, run `onSuccess` (page closes the dialog),
//   - on error: toast the surfaced error message.
//
// The tenant id is supplied by the caller (the page already knows which
// tenant row was clicked). The dialog is fully controlled.
import { toast } from 'sonner'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { VacateTenantForm } from '@/components/forms/VacateTenantForm'
import { useVacateTenant } from '@/api/tenants'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  tenantId: number | null
  tenantLabel?: string
  /** Fired after a successful vacate — the page typically closes the dialog. */
  onSuccess?: () => void
}

export function VacateTenantDialog({
  open,
  onOpenChange,
  tenantId,
  tenantLabel,
  onSuccess,
}: Props) {
  const vacate = useVacateTenant()

  const handleSubmit = (values: { lease_end: string }) => {
    if (tenantId == null) return
    vacate.mutate(
      { id: tenantId, leaseEnd: values.lease_end },
      {
        onSuccess: () => {
          toast.success('Tenant vacated')
          onSuccess?.()
        },
        onError: (err: unknown) => {
          const msg =
            err instanceof Error ? err.message : 'Failed to vacate tenant'
          toast.error(msg)
        },
      },
    )
  }

  const title = tenantLabel ? `Vacate ${tenantLabel}` : 'Vacate tenant'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Mark this tenant as vacated. This sets their lease end date and
            stops rent accrual from that day forward.
          </DialogDescription>
        </DialogHeader>
        <VacateTenantForm
          onSubmit={handleSubmit}
          isSubmitting={vacate.isPending}
        />
      </DialogContent>
    </Dialog>
  )
}
