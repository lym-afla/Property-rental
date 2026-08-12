import { afterEach, describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginPage } from './LoginPage'

function renderWithProviders(initialEntry: string | { pathname: string; state: unknown } = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function renderWithOidcNavigator(
  navigateToOidc: (url: string) => void,
  initialEntry: string | { pathname: string; state: unknown } = '/',
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <LoginPage navigateToOidc={navigateToOidc} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage', () => {
  afterEach(() => {
    delete window.__PROPERTY_RENTAL_CONFIG__
    window.sessionStorage.clear()
    vi.restoreAllMocks()
  })
  it('renders the form', () => {
    renderWithProviders()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument()
  })

  it('shows error on invalid credentials', async () => {
    const user = userEvent.setup()
    renderWithProviders()
    await user.type(screen.getByLabelText(/username/i), 'wrong')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /log in/i }))
    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument()
  })

  it('has a link to register', () => {
    renderWithProviders()
    expect(screen.getByRole('link', { name: /register/i })).toHaveAttribute('href', '/register')
  })

  it('automatically starts Authentik sign-in when local password auth is disabled', () => {
    window.__PROPERTY_RENTAL_CONFIG__ = {
      localPasswordAuthEnabled: false,
      oidcLoginUrl: '/oidc/authenticate/',
    }
    const replace = vi.fn()
    renderWithOidcNavigator(replace)
    expect(replace).toHaveBeenCalledWith('/oidc/authenticate/?next=%2F')
    expect(screen.getByRole('status', { name: /continuing to authentik/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /register/i })).not.toBeInTheDocument()
  })

  it('preserves the originally requested local URL in automatic Authentik sign-in', () => {
    window.__PROPERTY_RENTAL_CONFIG__ = {
      localPasswordAuthEnabled: false,
      oidcLoginUrl: '/oidc/authenticate/',
    }
    const replace = vi.fn()
    renderWithOidcNavigator(replace, {
      pathname: '/login',
      state: { from: '/properties/42?tab=rents' },
    })
    expect(replace).toHaveBeenCalledWith(
      '/oidc/authenticate/?next=%2Fproperties%2F42%3Ftab%3Drents',
    )
  })

  it('shows a manual retry instead of looping after the same automatic attempt returns', () => {
    window.__PROPERTY_RENTAL_CONFIG__ = {
      localPasswordAuthEnabled: false,
      oidcLoginUrl: '/oidc/authenticate/',
    }
    window.sessionStorage.setItem('property-rental:oidc-attempt', JSON.stringify({
      path: '/properties/42',
      timestamp: Date.now(),
    }))
    const replace = vi.fn()
    renderWithOidcNavigator(replace, { pathname: '/login', state: { from: '/properties/42' } })

    expect(replace).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: /try sign in with authentik again/i })).toHaveAttribute(
      'href',
      '/oidc/authenticate/?next=%2Fproperties%2F42',
    )
  })
})
