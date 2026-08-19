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
import { useTheme } from 'next-themes'
import { MonitorIcon, MoonIcon, SunIcon } from 'lucide-react'
import { useSession } from '@/context/SessionProvider'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
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
  const navigate = useNavigate()
  const { theme, setTheme } = useTheme()
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <div className="flex min-w-0 items-center gap-6">
            <span className="truncate font-semibold">Property Rental</span>
            <nav aria-label="Primary" className="hidden items-center gap-4 md:flex">
              {navItems.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `text-sm transition-colors hover:text-foreground ${isActive ? 'text-signal font-medium' : 'text-muted-foreground'}`
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
              <Button className="min-h-11 md:min-h-0" variant="ghost" size="sm" disabled={!user}>
                {user ? user.username : '—'}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-40">
              <DropdownMenuLabel>{user?.username}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => navigate('/profile')}>
                Profile
              </DropdownMenuItem>
              {/* Theme is a local device preference (next-themes storage),
                  unlike the backend-owned Life OS settings on /profile. */}
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>
                  {theme === 'dark' ? <MoonIcon aria-hidden="true" /> : theme === 'light' ? <SunIcon aria-hidden="true" /> : <MonitorIcon aria-hidden="true" />}
                  Theme
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent>
                  <DropdownMenuRadioGroup value={theme} onValueChange={setTheme}>
                    <DropdownMenuRadioItem value="light">Light</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="dark">Dark</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="system">System</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
              <DropdownMenuItem asChild variant="destructive">
                <a href="/oidc/logout/" role="link">Logout</a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6 pb-24 md:pb-6">
        <Outlet />
      </main>
      <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t bg-background/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex min-h-11 min-w-11 items-center justify-center overflow-hidden px-1 text-center text-[11px] leading-tight transition-colors ${isActive ? 'font-medium text-signal' : 'text-muted-foreground'}`
                  }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
