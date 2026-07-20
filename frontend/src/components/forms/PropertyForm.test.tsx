// Task 14 — Form tests for PropertyForm.
//
// Covers:
//   - Renders the expected fields on mount.
//   - Shows zod validation errors when required fields are empty.
//   - Calls onSubmit with the validated output shape on a valid submit.
//
// The form uses react-hook-form internally, so no providers are needed.
// The Currency `Select` (radix) defaults to 'USD', so a valid submit only
// requires `name` and `location`.
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PropertyForm } from './PropertyForm'

describe('PropertyForm', () => {
  it('renders the expected fields', () => {
    render(<PropertyForm onSubmit={() => {}} />)
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/address/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/bedrooms/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })

  it('shows zod validation errors when required fields are empty', async () => {
    const user = userEvent.setup()
    render(<PropertyForm onSubmit={() => {}} />)

    // Submit with empty default values to trigger zod validation.
    await user.click(screen.getByRole('button', { name: /save/i }))

    // Both Name and Location are required; zod surfaces both messages.
    // Multiple matching messages — use the AllBy variant.
    const messages = await screen.findAllByText('Required')
    expect(messages.length).toBeGreaterThanOrEqual(2)
  })

  it('calls onSubmit with the validated values on a valid submit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<PropertyForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText(/name/i), 'Riverside Flat')
    await user.type(screen.getByLabelText(/location/i), 'Berlin, DE')
    await user.click(screen.getByRole('button', { name: /save/i }))

    // handleSubmit invokes onSubmit with `(values, event)`. We assert the
    // first positional arg matches our validated payload.
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    expect(onSubmit.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        name: 'Riverside Flat',
        location: 'Berlin, DE',
        // Currency defaults to 'USD' and zod's coerced output keeps the enum.
        currency: 'USD',
        // num_bedrooms coerces to a number (zod output type).
        num_bedrooms: 0,
      }),
    )
  })
})
