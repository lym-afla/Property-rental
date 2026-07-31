import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useSession } from '@/context/SessionProvider'
import { Skeleton } from '@/components/ui/skeleton'

export function ProtectedRoute() {
  const location = useLocation()
  const { user, isLoading } = useSession()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Skeleton className="h-12 w-12 rounded-full" />
      </div>
    )
  }
  if (!user) {
    const from = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to="/login" replace state={{ from }} />
  }
  return <Outlet />
}
