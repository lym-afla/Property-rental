// frontend/src/components/modals/EntityFormDialog.tsx
//
// Generic shadcn Dialog wrapper for any of the entity forms
// (PropertyForm, TenantForm, TransactionForm, PropertyValuationForm).
//
// The caller decides:
//   - which form to render (`children` — typically a *Form component),
//   - what title to show (`title`),
//   - whether it's create or edit mode (`mode` — drives the title suffix),
//   - and what to do when the underlying mutation succeeds
//     (`onSuccess` — usually close + invalidate + toast, handled by the
//     page since the mutation hook itself already invalidates).
//
// The dialog is fully controlled via `open` / `onOpenChange` so the page
// owns the lifecycle (no internal state to drift out of sync).
import { type ReactNode } from 'react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  /** `create` appends "New" semantics to the title; `edit` appends "Edit". */
  mode?: 'create' | 'edit'
  /** The form body. The form is responsible for its own submit + reset. */
  children: ReactNode
}

export function EntityFormDialog({
  open,
  onOpenChange,
  title,
  description,
  mode,
  children,
}: Props) {
  const fullTitle = mode ? `${mode === 'create' ? 'New' : 'Edit'} ${title}` : title

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{fullTitle}</DialogTitle>
          {description ? (
            <DialogDescription>{description}</DialogDescription>
          ) : null}
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  )
}
