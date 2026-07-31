import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiFetch, startAuthorizationRefresh } from './client'

describe('apiFetch', () => {
  beforeEach(() => {
    // Set a fake CSRF cookie
    document.cookie = 'csrftoken=fake-csrf; path=/'
  })

  it('attaches CSRF header on POST', async () => {
    let capturedHeaders: Headers | undefined
    // Override fetch to capture headers
    const originalFetch = globalThis.fetch
    globalThis.fetch = ((_input: RequestInfo, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers)
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }) as typeof fetch

    await apiFetch('/test/', { method: 'POST', body: { x: 1 } })

    globalThis.fetch = originalFetch
    expect(capturedHeaders?.get('X-CSRFToken')).toBe('fake-csrf')
    expect(capturedHeaders?.get('Content-Type')).toBe('application/json')
  })

  it('does not attach CSRF on GET', async () => {
    let capturedHeaders: Headers | undefined
    const originalFetch = globalThis.fetch
    globalThis.fetch = ((_input: RequestInfo, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers)
      return Promise.resolve(new Response('null', { status: 200 }))
    }) as typeof fetch

    await apiFetch('/test/')

    globalThis.fetch = originalFetch
    expect(capturedHeaders?.get('X-CSRFToken')).toBeNull()
  })

  it('serializes query params', async () => {
    let capturedUrl = ''
    const originalFetch = globalThis.fetch
    globalThis.fetch = ((input: RequestInfo) => {
      capturedUrl = input.toString()
      return Promise.resolve(new Response('null', { status: 200 }))
    }) as typeof fetch

    await apiFetch('/test/', { query: { a: 1, b: 'hi', c: undefined } })
    globalThis.fetch = originalFetch
    expect(capturedUrl).toContain('a=1')
    expect(capturedUrl).toContain('b=hi')
    expect(capturedUrl).not.toContain('c=')
  })

  it('throws ApiError on non-2xx', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (() => Promise.resolve(new Response(JSON.stringify({ detail: 'nope' }), { status: 400 }))) as typeof fetch
    await expect(apiFetch('/test/')).rejects.toMatchObject({ name: 'ApiError', status: 400 })
    globalThis.fetch = originalFetch
  })

  it('dispatches auth:unauthorized event on 401', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (() => Promise.resolve(new Response('null', { status: 401 }))) as typeof fetch
    const events: string[] = []
    window.addEventListener('auth:unauthorized', () => events.push('fired'))
    await expect(apiFetch('/test/')).rejects.toThrow()
    globalThis.fetch = originalFetch
    expect(events).toEqual(['fired'])
  })

  it('navigates once and never replays a mutation requiring authorization refresh', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      code: 'authorization_refresh_required',
      refresh_url: '/oidc/authenticate/?next=%2Fproperties%2F42',
      retry: false,
    }), { status: 403, headers: { 'Content-Type': 'application/json' } }))
    globalThis.fetch = fetchMock
    const navigate = vi.fn()

    await expect(apiFetch('/properties/42/', {
      method: 'PATCH',
      body: { name: 'Updated' },
      startAuthorizationRefresh: navigate,
    })).rejects.toMatchObject({ status: 403 })

    expect(navigate).toHaveBeenCalledOnce()
    expect(navigate).toHaveBeenCalledWith('/oidc/authenticate/?next=%2Fproperties%2F42')
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('starts authorization refresh in the top-level browsing context', () => {
    const assign = vi.fn()
    vi.stubGlobal('window', { top: { location: { assign } } })
    startAuthorizationRefresh('/oidc/authenticate/?next=%2Fprofile')
    expect(assign).toHaveBeenCalledWith('/oidc/authenticate/?next=%2Fprofile')
    vi.unstubAllGlobals()
  })
})
