// frontend/src/pages/HomePage.tsx
//
// Minimal home page (Task 9 of Plan B2). The full dashboard arrives in
// Plan C; for now we surface two entity counts as entry points into the
// lists, plus a "coming soon" note. Counts come from the B1 hooks so the
// page stays consistent with the rest of the SPA — a 401 from the API
// surfaces through the normal SessionProvider redirect.
import { Link } from 'react-router-dom'

import { useProperties } from '@/api/properties'
import { useTenants } from '@/api/tenants'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export function HomePage() {
  const properties = useProperties()
  const tenants = useTenants()

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid gap-4 sm:grid-cols-2">
        <Link to="/properties" className="block">
          <Card className="transition-colors hover:bg-accent">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Properties
              </CardTitle>
            </CardHeader>
            <CardContent>
              {properties.isLoading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <div className="text-3xl font-bold">
                  {properties.data?.length ?? 0}
                </div>
              )}
            </CardContent>
          </Card>
        </Link>

        <Link to="/tenants" className="block">
          <Card className="transition-colors hover:bg-accent">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Tenants
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tenants.isLoading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <div className="text-3xl font-bold">
                  {tenants.data?.length ?? 0}
                </div>
              )}
            </CardContent>
          </Card>
        </Link>
      </div>

      <p className="text-sm text-muted-foreground">
        Dashboard coming soon.
      </p>
    </div>
  )
}
