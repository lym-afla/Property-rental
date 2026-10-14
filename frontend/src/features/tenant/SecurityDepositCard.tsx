// frontend/src/features/tenant/SecurityDepositCard.tsx
//
// "Security deposit" card on the tenant page: balance held at `asOf` plus the
// tenant's deposit movements with Add / Edit / Delete.
//
// Movement writes go through the mutation hooks' `mutateAsync` so the
// rejection (an `ApiError`) reaches `DepositMovementForm`, which maps server
// field errors inline. The hooks invalidate deposits, transactions, tenants
// and analytics, so no extra cache work is needed here.
import { useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { apiErrorMessage } from '@/api/client'

import {
  useCreateDepositMovement,
  useDeleteDepositMovement,
  useDepositBalance,
  useDepositMovements,
  useUpdateDepositMovement,
} from '@/api/deposits'
import {
  DepositMovementForm,
  type DepositMovementInput,
} from '@/components/forms/DepositMovementForm'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatCurrency, formatDate } from '@/lib/format'
import { transactionCategoryLabel } from '@/lib/transactionCategories'
import type { DepositKind, DepositMovement } from '@/types/deposit'
import type { Transaction } from '@/types/transaction'

const KIND_LABEL: Record<DepositKind, string> = {
  received: 'Received',
  returned: 'Returned',
  applied: 'Applied',
}

type Props = {
  tenantId: number
  propertyCurrency: string
  asOf: string
  /** The tenant's transactions; "Applied" movements may attach to one. */
  transactions: Transaction[]
}

export function SecurityDepositCard({
  tenantId,
  propertyCurrency,
  asOf,
  transactions,
}: Props) {
  const movementsQuery = useDepositMovements(tenantId)
  const balanceQuery = useDepositBalance({ tenantId, asOf })
  const createMovement = useCreateDepositMovement()
  const updateMovement = useUpdateDepositMovement()
  const deleteMovement = useDeleteDepositMovement()

  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState<DepositMovement | null>(null)
  const [deleting, setDeleting] = useState<DepositMovement | null>(null)

  const movements = movementsQuery.data ?? []
  const balances = balanceQuery.data?.balances ?? []

  // The deposit currency is fixed by any other existing movement; the one
  // being edited is excluded so a lone movement's currency can still change.
  const lockedCurrency = (excludeId?: number): string | null =>
    movements.find((m) => m.id !== excludeId)?.currency ?? null

  async function handleCreate(data: DepositMovementInput) {
    await createMovement.mutateAsync(data)
    toast.success('Deposit movement added')
    setCreateOpen(false)
  }

  async function handleUpdate(id: number, data: DepositMovementInput) {
    await updateMovement.mutateAsync({ id, data })
    toast.success('Deposit movement updated')
    setEditing(null)
  }

  async function handleDelete() {
    if (!deleting) return
    try {
      await deleteMovement.mutateAsync(deleting.id)
      toast.success('Deposit movement deleted')
      setDeleting(null)
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Failed to delete deposit movement'))
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Security deposit</CardTitle>
        <CardAction>
          <Button variant="outline" size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="space-y-1">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Held
          </dt>
          <dd className="text-sm font-medium">
            {balances.length === 0
              ? 'None held'
              : balances
                  .map((b) => formatCurrency(Number(b.amount), b.currency))
                  .join(' · ')}
          </dd>
        </dl>

        {movementsQuery.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : movementsQuery.isError ? (
          <ErrorState
            message="Failed to load deposit movements"
            onRetry={() => movementsQuery.refetch()}
          />
        ) : movements.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No deposit movements yet.
          </p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Applies to</TableHead>
                  <TableHead>Comment</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {movements.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>{formatDate(m.date)}</TableCell>
                    <TableCell>{KIND_LABEL[m.kind]}</TableCell>
                    <TableCell>
                      {formatCurrency(Number(m.amount), m.currency)}
                    </TableCell>
                    <TableCell>
                      {m.applied_to ? transactionCategoryLabel(m.applied_to) : '—'}
                    </TableCell>
                    <TableCell>{m.comment ?? ''}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label="Edit"
                          onClick={() => setEditing(m)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label="Delete"
                          onClick={() => setDeleting(m)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      <EntityFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Security deposit movement"
        mode="create"
      >
        <DepositMovementForm
          tenantId={tenantId}
          defaultCurrency={propertyCurrency}
          lockedCurrency={lockedCurrency()}
          candidateTransactions={transactions}
          onSubmit={handleCreate}
          onCancel={() => setCreateOpen(false)}
        />
      </EntityFormDialog>

      <EntityFormDialog
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null)
        }}
        title="Security deposit movement"
        mode="edit"
      >
        {editing && (
          <DepositMovementForm
            tenantId={tenantId}
            defaultCurrency={propertyCurrency}
            lockedCurrency={lockedCurrency(editing.id)}
            candidateTransactions={transactions}
            initial={editing}
            onSubmit={(data) => handleUpdate(editing.id, data)}
            onCancel={() => setEditing(null)}
          />
        )}
      </EntityFormDialog>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null)
        }}
        title="Delete deposit movement?"
        description="This cannot be undone. A transaction created by this movement is deleted with it."
        confirmText="Delete"
        confirmVariant="destructive"
        isLoading={deleteMovement.isPending}
        onConfirm={handleDelete}
      />
    </Card>
  )
}
