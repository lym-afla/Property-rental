import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { DepositMovement } from '@/types/deposit'
import type { Transaction } from '@/types/transaction'
import { DepositMovementForm } from './DepositMovementForm'

function tx(over: Partial<Transaction> & { id: number }): Transaction {
  return {
    property: 1,
    tenant: 7,
    date: '2026-03-01',
    category: 'rent',
    period: '2026-03',
    currency: 'USD',
    amount: '800.00',
    type: 'income',
    comment: null,
    deposit_movement: null,
    ...over,
  }
}

const candidates: Transaction[] = [
  tx({ id: 40, date: '2026-03-01', amount: '800.00' }),
  tx({ id: 41, date: '2026-04-01', amount: '810.00', deposit_movement: 99 }),
  tx({ id: 42, date: '2026-05-01', amount: '820.00', deposit_movement: 5 }),
  tx({ id: 43, date: '2026-06-01', amount: '150.00', category: 'repairs' }),
  tx({ id: 44, date: '2026-07-01', amount: '830.00', currency: 'EUR' }),
]

function setup(props: Partial<React.ComponentProps<typeof DepositMovementForm>> = {}) {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  const onCancel = vi.fn()
  render(
    <DepositMovementForm
      tenantId={7}
      defaultCurrency="USD"
      lockedCurrency={null}
      candidateTransactions={candidates}
      onSubmit={onSubmit}
      onCancel={onCancel}
      {...props}
    />,
  )
  return { onSubmit, onCancel, user: userEvent.setup() }
}

async function choose(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  option: string | RegExp,
) {
  await user.click(screen.getByRole('combobox', { name: label }))
  await user.click(await screen.findByRole('option', { name: option }))
}

const initialApplied: DepositMovement = {
  id: 5,
  tenant: 7,
  date: '2026-05-01',
  kind: 'applied',
  currency: 'USD',
  amount: '820.00',
  applied_to: 'rent',
  transaction: 42,
  owns_transaction: false,
  comment: null,
}

describe('DepositMovementForm', () => {
  it('hides applies-to and transaction for Received, shows them for Applied', async () => {
    const { user } = setup()
    expect(screen.queryByText('Applies to')).not.toBeInTheDocument()
    expect(screen.queryByText('Transaction')).not.toBeInTheDocument()

    await choose(user, 'Kind', 'Applied')
    expect(screen.getByRole('combobox', { name: 'Applies to' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Transaction' })).toBeInTheDocument()

    await choose(user, 'Kind', 'Returned')
    expect(screen.queryByText('Applies to')).not.toBeInTheDocument()
  })

  it('locks the currency input when a deposit currency exists', () => {
    setup({ lockedCurrency: 'EUR' })
    const input = screen.getByLabelText('Currency')
    expect(input).toHaveValue('EUR')
    expect(input).toHaveAttribute('readonly')
  })

  it('lets the user edit the currency when nothing is locked', () => {
    setup()
    const input = screen.getByLabelText('Currency')
    expect(input).toHaveValue('USD')
    expect(input).not.toHaveAttribute('readonly')
  })

  it('filters candidates by category, currency and existing links', async () => {
    const { user } = setup()
    await choose(user, 'Kind', 'Applied')
    await choose(user, 'Applies to', 'Rent')
    await user.click(screen.getByRole('combobox', { name: 'Transaction' }))
    const listbox = await screen.findByRole('listbox')
    const options = within(listbox).getAllByRole('option').map((o) => o.textContent)
    expect(options).toHaveLength(2)
    expect(options[0]).toBe('Create new transaction')
    expect(options[1]).toContain('2026-03-01')
    expect(options[1]).toContain('800.00')
    expect(options[1]).toContain('USD')
  })

  it('lists and selects the transaction already attached to the edited movement', async () => {
    const { user, onSubmit } = setup({ initial: initialApplied })
    expect(screen.getByRole('combobox', { name: 'Transaction' })).toHaveTextContent('2026-05-01')
    expect(screen.getByLabelText('Date')).toBeDisabled()

    await user.click(screen.getByRole('combobox', { name: 'Transaction' }))
    const listbox = await screen.findByRole('listbox')
    const options = within(listbox).getAllByRole('option').map((o) => o.textContent)
    expect(options.some((t) => t?.includes('820.00'))).toBe(true)
    expect(options.some((t) => t?.includes('810.00'))).toBe(false)
    await user.keyboard('{Escape}')

    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ transaction: 42, applied_to: 'rent' })
  })

  it('keeps the date editable and the transaction fixed for an owned movement', () => {
    setup({ initial: { ...initialApplied, owns_transaction: true } })
    expect(screen.getByLabelText('Date')).toBeEnabled()
    expect(screen.getByRole('combobox', { name: 'Transaction' })).toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'Transaction' })).toHaveTextContent('2026-05-01')
  })

  it('choosing a candidate sets and disables the date', async () => {
    const { user, onSubmit } = setup()
    await choose(user, 'Kind', 'Applied')
    await choose(user, 'Applies to', 'Rent')
    await user.type(screen.getByLabelText('Amount'), '800.00')
    await choose(user, 'Transaction', /2026-03-01/)
    expect(screen.getByLabelText('Date')).toHaveValue('2026-03-01')
    expect(screen.getByLabelText('Date')).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      date: '2026-03-01',
      transaction: 40,
      kind: 'applied',
      applied_to: 'rent',
    })
  })

  it('submits transaction null for "Create new transaction" and nulls for non-applied kinds', async () => {
    const { user, onSubmit } = setup()
    await user.type(screen.getByLabelText('Date'), '2026-02-01')
    await user.type(screen.getByLabelText('Amount'), '1000.00')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
    expect(onSubmit.mock.calls[0][0]).toEqual({
      tenant: 7,
      date: '2026-02-01',
      kind: 'received',
      currency: 'USD',
      amount: '1000.00',
      applied_to: null,
      transaction: null,
      comment: null,
    })

    await choose(user, 'Kind', 'Applied')
    await choose(user, 'Applies to', 'Cost reimbursement')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2))
    expect(onSubmit.mock.calls[1][0]).toMatchObject({
      kind: 'applied',
      applied_to: 'cost_reimbursement',
      transaction: null,
    })
  })

  it('shows list-shaped server errors under the field', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError(400, { amount: ['Exceeds balance.'] }))
    const { user } = setup({ onSubmit })
    await user.type(screen.getByLabelText('Date'), '2026-02-01')
    await user.type(screen.getByLabelText('Amount'), '5')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Exceeds balance.')).toBeInTheDocument()
  })

  it('shows string-shaped server errors on the transaction field', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError(400, { transaction: 'Already linked.' }))
    const { user } = setup({ onSubmit, initial: initialApplied })
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Already linked.')).toBeInTheDocument()
  })

  it('calls onCancel', async () => {
    const { user, onCancel } = setup()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalled()
  })
})
