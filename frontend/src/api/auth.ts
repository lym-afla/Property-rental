import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, ApiError } from './client'
import { queryKeys } from './keys'
import type { User } from '@/types/user'

type MeResponse = { user: User }

export function useMe() {
  return useQuery<User | null>({
    queryKey: queryKeys.auth.me,
    queryFn: async () => {
      try {
        const data = await apiFetch<MeResponse>('/auth/me/')
        return data.user
      } catch (err: unknown) {
        // DRF's SessionAuthentication returns 403 (not 401) for anonymous
        // requests — there's no WWW-Authenticate header to set. Treat both
        // as "no session" so the SPA falls back to the login redirect.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return null
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
      qc.setQueryData(queryKeys.auth.me, data.user)
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
      qc.setQueryData(queryKeys.auth.me, data.user)
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
