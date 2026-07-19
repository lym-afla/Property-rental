import { Outlet } from 'react-router-dom'
import { useSession } from '@/context/SessionProvider'
import { useLogout } from '@/api/auth'
import { Button } from '@/components/ui/button'

export function AppLayout() {
  const { user } = useSession()
  const logout = useLogout()
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <span className="font-semibold">Property Rental</span>
          <div className="flex items-center gap-4">
            {user && <span className="text-sm text-muted-foreground">{user.username}</span>}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
            >
              {logout.isPending ? 'Logging out…' : 'Logout'}
            </Button>
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
