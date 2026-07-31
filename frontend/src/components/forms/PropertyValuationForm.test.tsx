import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PropertyValuationForm } from './PropertyValuationForm'

describe('PropertyValuationForm', () => {
  it('uses plain valuation labels and defaults blank debt to zero on submit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<PropertyValuationForm onSubmit={onSubmit} />)

    expect(screen.getByLabelText('Date')).toBeInTheDocument()
    expect(screen.getByLabelText('Total value')).toBeInTheDocument()
    expect(screen.getByLabelText('Debt')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Date'), '2026-07-31')
    await user.type(screen.getByLabelText('Total value'), '250000')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    expect(onSubmit).toHaveBeenCalledWith({
      capital_structure_date: '2026-07-31',
      capital_structure_value: '250000',
      capital_structure_debt: '0',
    }, expect.anything())
  })
})
