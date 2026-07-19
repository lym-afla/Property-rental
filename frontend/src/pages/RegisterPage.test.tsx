import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RegisterPage } from './RegisterPage'

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RegisterPage', () => {
  it('renders the form', () => {
    renderWithProviders()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getAllByLabelText(/password/i)).toHaveLength(2)  // password + confirm
  })

  it('rejects mismatched passwords locally', async () => {
    const user = userEvent.setup()
    renderWithProviders()
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/email/i), 'new@example.com')
    const passwords = screen.getAllByLabelText(/password/i)
    await user.type(passwords[0], 'StrongPass123!')
    await user.type(passwords[1], 'DifferentPass123!')
    await user.click(screen.getByRole('button', { name: /register/i }))
    expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument()
  })

  it('shows server error on duplicate username', async () => {
    const user = userEvent.setup()
    renderWithProviders()
    await user.type(screen.getByLabelText(/username/i), 'taken')
    await user.type(screen.getByLabelText(/email/i), 'x@example.com')
    const passwords = screen.getAllByLabelText(/password/i)
    await user.type(passwords[0], 'StrongPass123!')
    await user.type(passwords[1], 'StrongPass123!')
    await user.click(screen.getByRole('button', { name: /register/i }))
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument()
  })
})
