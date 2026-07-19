import { Navigate, Outlet } from 'react-router-dom'
import { useSession } from '@/context/SessionProvider'
import { Skeleton } from '@/components/ui/skeleton'

export function ProtectedRoute() {
  const { user, isLoading } = useSession()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Skeleton className="h-12 w-12 rounded-full" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}
