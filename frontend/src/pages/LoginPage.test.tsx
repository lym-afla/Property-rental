import { describe, it, expect } from 'vitest'
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

describe('LoginPage', () => {
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

  it('renders only the Authentik sign-in action when local password auth is disabled', () => {
    window.__PROPERTY_RENTAL_CONFIG__ = {
      localPasswordAuthEnabled: false,
      oidcLoginUrl: '/oidc/authenticate/',
    }
    renderWithProviders()
    expect(screen.getByRole('link', { name: /sign in with authentik/i })).toHaveAttribute(
      'href',
      '/oidc/authenticate/?next=%2F',
    )
    expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /register/i })).not.toBeInTheDocument()
    delete window.__PROPERTY_RENTAL_CONFIG__
  })

  it('preserves the originally requested local URL in the Authentik action', () => {
    window.__PROPERTY_RENTAL_CONFIG__ = {
      localPasswordAuthEnabled: false,
      oidcLoginUrl: '/oidc/authenticate/',
    }
    renderWithProviders({
      pathname: '/login',
      state: { from: '/properties/42?tab=rents' },
    })
    expect(screen.getByRole('link', { name: /sign in with authentik/i })).toHaveAttribute(
      'href',
      '/oidc/authenticate/?next=%2Fproperties%2F42%3Ftab%3Drents',
    )
    delete window.__PROPERTY_RENTAL_CONFIG__
  })
})
