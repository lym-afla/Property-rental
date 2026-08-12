import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import { useMe } from '@/api/auth'
import { queryKeys } from '@/api/keys'
import { clearOidcAttempt } from '@/api/oidcAttempt'
import type { User } from '@/types/user'

type SessionContextValue = {
  user: User | null
  isLoading: boolean
}

const SessionContext = createContext<SessionContextValue>({ user: null, isLoading: true })

export function SessionProvider({
  children,
  reload = () => window.location.reload(),
}: {
  children: ReactNode
  reload?: () => void
}) {
  const queryClient = useQueryClient()
  const { data: user, isLoading, isFetching } = useMe()

  useEffect(() => {
    if (user) clearOidcAttempt()
  }, [user])

  // A later 401 is authoritative: hide identity immediately and discard all
  // user-scoped query data before any protected chrome can render again.
  useEffect(() => {
    const handler = () => {
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== 'auth',
      })
      queryClient.setQueryData(queryKeys.auth.me, null)
    }
    window.addEventListener('auth:unauthorized', handler)
    return () => window.removeEventListener('auth:unauthorized', handler)
  }, [queryClient])

  useEffect(() => {
    const revalidateRestoredPage = (event: PageTransitionEvent) => {
      if (event.persisted) reload()
    }
    window.addEventListener('pageshow', revalidateRestoredPage)
    return () => window.removeEventListener('pageshow', revalidateRestoredPage)
  }, [reload])

  // Task 13: prime the CSRF cookie on app boot. Django's
  // ``CsrfViewMiddleware`` only stamps ``csrftoken`` on HTML responses, but
  // this SPA consumes JSON — so the cookie would never arrive without an
  // explicit fetch of ``/auth/csrf/`` (which carries
  // ``@ensure_csrf_cookie``). Fire-and-forget: the response body is
  // irrelevant; the ``Set-Cookie`` header is what matters. Without this,
  // the SPA's first mutation (e.g. logout) returns HTTP 403.
  useEffect(() => {
    // Intentionally swallowed — a failed prime (e.g. transient network
    // blip) must NOT crash the SPA on boot. Mutations will still surface
    // their own errors via React Query when they happen.
    apiFetch('/auth/csrf/').catch(() => { /* cookie will retry on next mutation */ })
  }, [])

  return (
    <SessionContext.Provider value={{ user: user ?? null, isLoading: isLoading || isFetching }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  return useContext(SessionContext)
}
