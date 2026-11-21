import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { LoanPaymentForm } from './LoanPaymentForm'

it('records total and interest without silently rounding entered amounts', async () => {
  const user = userEvent.setup()
  const submit = vi.fn()
  render(<LoanPaymentForm onSubmit={submit} />)
  await user.type(screen.getByLabelText('Payment date'), '2026-10-15')
  await user.type(screen.getByLabelText('Interest'), '125.12')
  await user.type(screen.getByLabelText('Total payment'), '400.99')
  await user.click(screen.getByRole('button', { name: 'Save payment' }))
  await waitFor(() => expect(submit).toHaveBeenCalledWith({date:'2026-10-15', interest:'125.12', total:'400.99', comment:''}))
})

it('supports interest and principal entry and rejects total below interest', async () => {
  const user = userEvent.setup()
  const submit = vi.fn()
  render(<LoanPaymentForm onSubmit={submit} />)
  await user.type(screen.getByLabelText('Payment date'), '2026-10-15')
  await user.type(screen.getByLabelText('Interest'), '500')
  await user.type(screen.getByLabelText('Total payment'), '400')
  await user.click(screen.getByRole('button', { name: 'Save payment' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Total must be at least the interest')
  expect(submit).not.toHaveBeenCalled()
  await user.selectOptions(screen.getByLabelText('Enter payment as'), 'principal')
  await user.type(screen.getByLabelText('Principal'), '100.25')
  await user.click(screen.getByRole('button', { name: 'Save payment' }))
  await waitFor(() => expect(submit).toHaveBeenCalledWith({date:'2026-10-15', interest:'500', principal:'100.25', comment:''}))
})
