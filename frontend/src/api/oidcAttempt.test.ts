import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearOidcAttempt, hasRecentOidcAttempt, recordOidcAttempt } from './oidcAttempt'

describe('OIDC attempt guard', () => {
  afterEach(() => { sessionStorage.clear(); vi.useRealTimers() })

  it('rejects a future timestamp instead of treating it as recent', () => {
    vi.setSystemTime(new Date('2026-08-12T10:00:00Z'))
    recordOidcAttempt('/properties/42', Date.now() + 1_000)
    expect(hasRecentOidcAttempt('/properties/42', Date.now())).toBe(false)
  })

  it('accepts only a nonnegative age below thirty seconds', () => {
    expect(hasRecentOidcAttempt('/properties/42', 30_000)).toBe(false)
    recordOidcAttempt('/properties/42', 1)
    expect(hasRecentOidcAttempt('/properties/42', 30_000)).toBe(true)
    expect(hasRecentOidcAttempt('/properties/42', 30_001)).toBe(false)
  })

  it('clears the guard after an authenticated entry', () => {
    recordOidcAttempt('/', 1)
    clearOidcAttempt()
    expect(hasRecentOidcAttempt('/', 2)).toBe(false)
  })
})
