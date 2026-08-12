const OIDC_ATTEMPT_KEY = 'property-rental:oidc-attempt'
const OIDC_LOOP_WINDOW_MS = 30_000

export function recordOidcAttempt(path: string, timestamp = Date.now()) {
  window.sessionStorage.setItem(OIDC_ATTEMPT_KEY, JSON.stringify({ path, timestamp }))
}

export function hasRecentOidcAttempt(path: string, now = Date.now()) {
  try {
    const attempt = JSON.parse(window.sessionStorage.getItem(OIDC_ATTEMPT_KEY) ?? 'null') as {
      path?: unknown
      timestamp?: unknown
    } | null
    if (attempt?.path !== path || typeof attempt.timestamp !== 'number') return false
    const age = now - attempt.timestamp
    return age >= 0 && age < OIDC_LOOP_WINDOW_MS
  } catch {
    clearOidcAttempt()
    return false
  }
}

export function clearOidcAttempt() {
  window.sessionStorage.removeItem(OIDC_ATTEMPT_KEY)
}
