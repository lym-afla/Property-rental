import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/handlers'
import { queryKeys } from '@/api/keys'
import { SessionProvider, useSession } from './SessionProvider'

function SessionState() {
  const { user, isLoading } = useSession()
  return <p>{isLoading ? 'checking' : user ? user.username : 'anonymous'}</p>
}

describe('SessionProvider', () => {
  it('clears cached identity and user data immediately on a later 401', async () => {
    // Break caught: making the unauthorized event handler a no-op leaves
    // authenticated chrome and cached business data visible after logout.
    server.use(
      http.get('/api/v1/auth/me/', () => HttpResponse.json({ user: {
        id: 1, username: 'alice', email: 'alice@example.test', first_name: '',
        last_name: '', default_currency: 'USD', chart_frequency: 'M',
        chart_timeline: 12, digits: 2, use_default_currency_for_all_data: false,
      } })),
    )
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    qc.setQueryData(queryKeys.properties.all, [{ id: 1, name: 'Private home' }])

    render(
      <QueryClientProvider client={qc}>
        <SessionProvider><SessionState /></SessionProvider>
      </QueryClientProvider>,
    )
    await screen.findByText('alice')

    window.dispatchEvent(new CustomEvent('auth:unauthorized'))

    await screen.findByText('anonymous')
    await waitFor(() => {
      expect(qc.getQueryData(queryKeys.properties.all)).toBeUndefined()
    })
  })

  it('revalidates a protected page restored from the browser back-forward cache', async () => {
    const reload = vi.fn()
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <SessionProvider reload={reload}><SessionState /></SessionProvider>
      </QueryClientProvider>,
    )
    await screen.findByText('alice')
    const event = new Event('pageshow')
    Object.defineProperty(event, 'persisted', { value: true })

    fireEvent(window, event)

    expect(reload).toHaveBeenCalledOnce()
  })

  it('does not reload on an ordinary page show', async () => {
    const reload = vi.fn()
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <SessionProvider reload={reload}><SessionState /></SessionProvider>
      </QueryClientProvider>,
    )
    await screen.findByText('alice')
    const event = new Event('pageshow')
    Object.defineProperty(event, 'persisted', { value: false })

    fireEvent(window, event)

    expect(reload).not.toHaveBeenCalled()
  })
})
