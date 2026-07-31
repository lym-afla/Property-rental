import {
  useQuery,
  useMutation,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { apiFetch, ApiError } from './client'
import { queryKeys } from './keys'
import type { User } from '@/types/user'

type MeResponse = { user: User }

export type RuntimeConfig = {
  localPasswordAuthEnabled: boolean
  oidcLoginUrl: string
}

declare global {
  interface Window {
    __PROPERTY_RENTAL_CONFIG__?: RuntimeConfig
  }
}

export function getRuntimeConfig(): RuntimeConfig {
  return window.__PROPERTY_RENTAL_CONFIG__ ?? {
    localPasswordAuthEnabled: true,
    oidcLoginUrl: '/oidc/authenticate/',
  }
}

export function getOidcLoginUrl(nextPath = '/'): string {
  const { oidcLoginUrl } = getRuntimeConfig()
  const separator = oidcLoginUrl.includes('?') ? '&' : '?'
  return `${oidcLoginUrl}${separator}${new URLSearchParams({ next: nextPath })}`
}

function removeUserScopedQueryData(qc: QueryClient) {
  qc.removeQueries({
    predicate: (query) => query.queryKey[0] !== 'auth',
  })
}

function replaceAuthenticatedSession(qc: QueryClient, user: User) {
  removeUserScopedQueryData(qc)
  qc.setQueryData(queryKeys.auth.me, user)
}

function removeDataOnIdentityChange(qc: QueryClient, user: User | null) {
  const current = qc.getQueryData<User | null>(queryKeys.auth.me)
  if (current?.id !== user?.id) removeUserScopedQueryData(qc)
}

export function useMe() {
  const qc = useQueryClient()
  return useQuery<User | null>({
    queryKey: queryKeys.auth.me,
    queryFn: async () => {
      try {
        const data = await apiFetch<MeResponse>('/auth/me/')
        removeDataOnIdentityChange(qc, data.user)
        return data.user
      } catch (err: unknown) {
        // DRF's SessionAuthentication returns 403 (not 401) for anonymous
        // requests — there's no WWW-Authenticate header to set. Treat both
        // as "no session" so the SPA falls back to the login redirect.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          removeDataOnIdentityChange(qc, null)
          return null
        }
        throw err
      }
    },
    retry: false,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { username: string; password: string }) =>
      apiFetch<MeResponse>('/auth/login/', { method: 'POST', body: vars }),
    onSuccess: (data) => {
      replaceAuthenticatedSession(qc, data.user)
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/auth/logout/', { method: 'POST' }),
    onSettled: () => {
      qc.setQueryData(queryKeys.auth.me, null)
      qc.clear()
    },
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { username: string; password: string; email: string }) =>
      apiFetch<MeResponse>('/auth/register/', { method: 'POST', body: vars }),
    onSuccess: (data) => {
      replaceAuthenticatedSession(qc, data.user)
    },
  })
}

// PATCH /auth/me/ — partial update of the current user's settings
// (default_currency, chart_frequency, chart_timeline, digits,
// use_default_currency_for_all_data, etc.). Response shape matches
// `MeView.get` (`{user}`), so we prime the cache with the new user.
export function useUpdateMe() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: Partial<User>) =>
      apiFetch<MeResponse>('/auth/me/', { method: 'PATCH', body: vars }),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.auth.me, data.user)
    },
  })
}

// POST /auth/change-password/ — wraps Django's PasswordChangeForm.
// `update_session_auth_hash` keeps the current session valid after the
// hash rotates, so no cache wipe / re-login is needed on success.
export function useChangePassword() {
  return useMutation({
    mutationFn: (vars: {
      old_password: string
      new_password1: string
      new_password2: string
    }) =>
      apiFetch<{ detail: string }>('/auth/change-password/', {
        method: 'POST',
        body: vars,
      }),
  })
}
