import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { apiFetch } from '@/api/client'
import { useMe } from '@/api/auth'
import type { User } from '@/types/user'

type SessionContextValue = {
  user: User | null
  isLoading: boolean
}

const SessionContext = createContext<SessionContextValue>({ user: null, isLoading: true })

export function SessionProvider({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useMe()

  // Listen for 401 events from the API client and refetch.
  useEffect(() => {
    const handler = () => { /* React Query will refetch on next query invalidation */ }
    window.addEventListener('auth:unauthorized', handler)
    return () => window.removeEventListener('auth:unauthorized', handler)
  }, [])

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
    <SessionContext.Provider value={{ user: user ?? null, isLoading }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  return useContext(SessionContext)
}
