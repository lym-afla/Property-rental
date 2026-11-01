export type TenantStatus = 'active' | 'will-vacate' | 'vacated'

export function tenantStatus(leaseEnd: string | null | undefined): TenantStatus {
  if (!leaseEnd) return 'active'
  const today = new Date().toISOString().slice(0, 10)
  return leaseEnd < today ? 'vacated' : 'will-vacate'
}
