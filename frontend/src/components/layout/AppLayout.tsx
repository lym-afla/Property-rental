// frontend/src/components/layout/AppLayout.tsx
//
// Top-level chrome (navbar + content outlet) for the authenticated app.
//
// Task 12: the "Profile" link moved OUT of the main nav and INTO a
// dropdown anchored under the username (right side of the navbar). The
// dropdown surfaces Profile + Logout — the two account-scoped actions —
// so the primary nav stays focused on the data surfaces (Dashboard,
// Properties, Tenants, Transactions, FX).
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useSession } from '@/context/SessionProvider'
import { useLogout } from '@/api/auth'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/properties', label: 'Properties' },
  { to: '/tenants', label: 'Tenants' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/fx', label: 'FX' },
]

export function AppLayout() {
  const { user } = useSession()
  const logout = useLogout()
  const navigate = useNavigate()
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
          {/* Account dropdown — Profile + Logout live under the username
              so the primary nav carries only data surfaces. */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" disabled={!user}>
                {user ? user.username : '—'}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-40">
              <DropdownMenuLabel>{user?.username}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => navigate('/profile')}>
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onSelect={() => logout.mutate()}
                disabled={logout.isPending}
              >
                {logout.isPending ? 'Logging out…' : 'Logout'}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
