import { afterEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import { http, HttpResponse } from 'msw'
import { AppLayout } from './AppLayout'
import { SessionProvider } from '@/context/SessionProvider'
import { server } from '@/test/handlers'

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <MemoryRouter>
          <SessionProvider>
            <Routes>
              <Route element={<AppLayout />}>
                <Route index element={<p>Dashboard</p>} />
              </Route>
            </Routes>
          </SessionProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('AppLayout logout', () => {
  it('uses the OIDC logout link without posting to the local logout API', async () => {
    // Break caught: changing the visible production logout action back to a
    // client-side mutation would remove this link and issue a local POST.
    let localLogoutPosts = 0
    server.use(
      http.post('/api/v1/auth/logout/', () => {
        localLogoutPosts += 1
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderLayout()
    await user.click(await screen.findByRole('button', { name: 'alice' }))

    const logout = screen.getByRole('link', { name: 'Logout' })
    expect(logout).toHaveAttribute('href', '/oidc/logout/')

    // Keep jsdom on this document; a browser follows the anchor normally.
    logout.addEventListener('click', event => event.preventDefault(), { once: true })
    await user.click(logout)
    expect(localLogoutPosts).toBe(0)
  })
})

describe('AppLayout theme', () => {
  afterEach(() => {
    document.documentElement.classList.remove('dark')
    localStorage.removeItem('theme')
  })

  it('switches the document to dark mode from the account dropdown', async () => {
    const user = userEvent.setup()

    renderLayout()
    await user.click(await screen.findByRole('button', { name: 'alice' }))
    // Radix submenus do not select via synthetic mouse clicks in jsdom;
    // open the submenu, focus the item, and confirm with the keyboard.
    await user.click(screen.getByRole('menuitem', { name: /Theme/ }))
    const darkItem = await screen.findByRole('menuitemradio', { name: 'Dark' })
    darkItem.focus()
    await user.keyboard('[Enter]')

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('theme')).toBe('dark')
  })
})
