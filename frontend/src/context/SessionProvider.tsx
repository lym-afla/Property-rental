import { createContext, useContext, useEffect, type ReactNode } from 'react'
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

  return (
    <SessionContext.Provider value={{ user: user ?? null, isLoading }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  return useContext(SessionContext)
}
