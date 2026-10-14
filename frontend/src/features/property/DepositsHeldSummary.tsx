// frontend/src/features/property/DepositsHeldSummary.tsx
//
// "Deposits held" summary on the property page: the security deposit each
// tenant has on hand at `asOf` (linked to the tenant page), followed by a
// total per currency. It is an optional summary, so it renders nothing while
// loading, on error, or when no deposit has ever been held.
import { Link } from 'react-router-dom'

import { useDepositBalance } from '@/api/deposits'
import { formatCurrency } from '@/lib/format'

type Props = {
  propertyId: number
  asOf: string
  tenants: { id: number; name: string }[]
}

export function DepositsHeldSummary({ propertyId, asOf, tenants }: Props) {
  const { data } = useDepositBalance({ propertyId, asOf })

  if (!data || data.balances.length === 0) return null

  const nameById = new Map(tenants.map((t) => [t.id, t.name]))

  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold">Deposits held</h2>
      <ul className="space-y-1 text-sm">
        {(data.by_tenant ?? []).map((b) => (
          <li
            key={`${b.tenant}-${b.currency}`}
            className="flex justify-between gap-4"
          >
            <Link to={`/tenants/${b.tenant}`} className="hover:underline">
              {nameById.get(b.tenant) ?? `Tenant #${b.tenant}`}
            </Link>
            <span>{formatCurrency(Number(b.amount), b.currency)}</span>
          </li>
        ))}
        {data.balances.map((b) => (
          <li
            key={`total-${b.currency}`}
            className="flex justify-between gap-4 border-t pt-1 font-medium"
          >
            <span>Total</span>
            <span>{formatCurrency(Number(b.amount), b.currency)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
