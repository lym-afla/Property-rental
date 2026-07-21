import { NavLink, Outlet } from 'react-router-dom'
import { useSession } from '@/context/SessionProvider'
import { useLogout } from '@/api/auth'
import { Button } from '@/components/ui/button'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/properties', label: 'Properties' },
  { to: '/tenants', label: 'Tenants' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/fx', label: 'FX' },
  { to: '/profile', label: 'Profile' },
]

export function AppLayout() {
  const { user } = useSession()
  const logout = useLogout()
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <span className="font-semibold">Property Rental</span>
            <nav className="flex items-center gap-4">
              {navItems.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `text-sm transition-colors hover:text-foreground ${isActive ? 'text-foreground font-medium' : 'text-muted-foreground'}`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
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
