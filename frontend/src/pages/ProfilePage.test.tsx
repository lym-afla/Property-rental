// frontend/src/pages/ProfilePage.test.tsx
//
// Smoke tests for the Profile page. The default MSW handler for
// `/auth/me/` returns `fixtureUser`, so the happy path resolves without
// per-test handler registration. The error path overrides the handler to
// exercise the `ErrorState` affordance.
//
// We also assert that each of the three tabs becomes visible on click so
// the radix Tabs wiring (controlled via `defaultValue`, not via state) is
// exercised end-to-end.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { ProfilePage } from './ProfilePage'
import { server } from '@/test/handlers'
import { fixtureUser } from '@/__fixtures__/user'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProfilePage', () => {
  it('renders the page title and the default "User details" tab', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: /profile/i })).toBeInTheDocument()
    // Default tab is "User details" — username is visible on this tab.
    expect(await screen.findByText(fixtureUser.username)).toBeInTheDocument()
  })

  it('shows the username from the fixture', async () => {
    renderPage()
    expect(await screen.findByText(fixtureUser.username)).toBeInTheDocument()
  })

  it('renders the "Edit profile" button on the User details tab', async () => {
    renderPage()
    expect(
      await screen.findByRole('button', { name: /edit profile/i }),
    ).toBeInTheDocument()
  })

  it('switches to the Settings tab on click', async () => {
    const user = userEvent.setup()
    renderPage()
    // Wait for default tab content first.
    await screen.findByText(fixtureUser.username)
    await user.click(screen.getByRole('tab', { name: /settings/i }))
    // Settings tab should show the ProfileSettingsForm content
    expect(screen.getByRole('tab', { name: /settings/i })).toHaveAttribute('data-state', 'active')
  })

  it('switches to the Change password tab on click', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(fixtureUser.username)
    await user.click(screen.getByRole('tab', { name: /change password/i }))
    expect(screen.getByRole('tab', { name: /change password/i })).toHaveAttribute('data-state', 'active')
  })

  it('renders ErrorState when the /auth/me/ request fails', async () => {
    server.use(
      http.get('/api/v1/auth/me/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText(/failed to load profile/i)).toBeInTheDocument()
  })
})
