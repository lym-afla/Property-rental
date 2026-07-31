import type { User } from '@/types/user'

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  startAuthorizationRefresh?: (refreshUrl: string) => void
}

type RefreshResponse = {
  code: 'authorization_refresh_required'
  refresh_url: string
  retry: false
}

export function startAuthorizationRefresh(refreshUrl: string): void {
  const topLevelWindow = window.top ?? window
  topLevelWindow.location.assign(refreshUrl)
}

function isAuthorizationRefreshResponse(body: unknown): body is RefreshResponse {
  if (!body || typeof body !== 'object') return false
  const value = body as Record<string, unknown>
  return value.code === 'authorization_refresh_required'
    && typeof value.refresh_url === 'string'
    && value.retry === false
}

function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    body,
    query,
    headers,
    startAuthorizationRefresh: navigate = startAuthorizationRefresh,
    ...rest
  } = options

  const search = query
    ? '?' + new URLSearchParams(
        Object.entries(query)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : ''

  const method = (rest.method ?? 'GET').toUpperCase()
  const isMutation = method !== 'GET' && method !== 'HEAD'

  const finalHeaders: Record<string, string> = {
    ...(headers as Record<string, string>),
  }
  if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json'
  }
  if (isMutation) {
    const csrf = getCsrfToken()
    if (csrf) finalHeaders['X-CSRFToken'] = csrf
  }

  const response = await fetch(`/api/v1${path}${search}`, {
    ...rest,
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  })

  if (response.status === 401) {
    // Session expired — SessionProvider (Task 7) will pick this up via an event.
    window.dispatchEvent(new CustomEvent('auth:unauthorized'))
  }

  if (!response.ok) {
    let errorBody: unknown
    try {
      errorBody = await response.json()
    } catch {
      errorBody = await response.text()
    }
    if (response.status === 403 && isAuthorizationRefreshResponse(errorBody)) {
      navigate(errorBody.refresh_url)
    }
    throw new ApiError(response.status, errorBody)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

// Convenience for the SessionProvider to clear on 401.
export type { User }
