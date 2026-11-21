import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PropertyValuationForm } from './PropertyValuationForm'

describe('PropertyValuationForm', () => {
  it('preserves a valuation-only observation without inventing a debt payoff', async () => {
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
      capital_structure_debt: null,
    }, expect.anything())
  })
})

it('requires a loan for a nonzero debt and submits the chosen loan', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<PropertyValuationForm onSubmit={onSubmit} loans={[{id: 7, property: 1, lender: 'Example Bank', currency: 'GBP', reference: '', start_date: '2020-01-01', end_date: null, original_principal: null, interest_rate: null, rate_type: '', created_at: '', updated_at: ''}]} />)
  await user.type(screen.getByLabelText('Date'), '2026-07-31')
  await user.type(screen.getByLabelText('Total value'), '250000')
  await user.type(screen.getByLabelText('Debt'), '100000')
  await user.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Select a loan for a non-zero debt balance')).toBeInTheDocument()
  expect(onSubmit).not.toHaveBeenCalled()
  await user.selectOptions(screen.getByLabelText('Loan for debt balance'), '7')
  await user.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({capital_structure_date:'2026-07-31', capital_structure_value:'250000', capital_structure_debt:'100000', loan:7}, expect.anything()))
})

it('edits a debt-only observation without inventing a property valuation', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<PropertyValuationForm defaultValues={{capital_structure_date:'2026-07-31', capital_structure_value:'', capital_structure_debt:'100000',loan:7}} loans={[{id:7,property:1,lender:'Example Bank',currency:'GBP',reference:'',start_date:'2020-01-01',end_date:null,original_principal:null,interest_rate:null,rate_type:'',created_at:'',updated_at:''}]} onSubmit={onSubmit} />)
  await user.clear(screen.getByLabelText('Debt'))
  await user.type(screen.getByLabelText('Debt'), '99500')
  await user.click(screen.getByRole('button', {name:'Save'}))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({capital_structure_date:'2026-07-31', capital_structure_value:null, capital_structure_debt:'99500',loan:7}, expect.anything()))
})

it('requires an observation value or an explicitly supplied debt, including zero', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<PropertyValuationForm defaultValues={{capital_structure_date:'2026-07-31'}} onSubmit={onSubmit} />)
  await user.click(screen.getByRole('button', {name:'Save'}))
  expect(await screen.findByText('Enter a total value or a debt balance')).toBeInTheDocument()
  expect(onSubmit).not.toHaveBeenCalled()
  await user.type(screen.getByLabelText('Debt'), '0')
  await user.click(screen.getByRole('button', {name:'Save'}))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({capital_structure_date:'2026-07-31', capital_structure_value:null, capital_structure_debt:'0'}, expect.anything()))
})

it('preserves a null debt when editing an imported valuation-only observation', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<PropertyValuationForm defaultValues={{capital_structure_date:'2026-07-31',capital_structure_value:'250000',capital_structure_debt:null}} onSubmit={onSubmit} />)
  expect(screen.getByLabelText('Debt')).toHaveValue('')
  await user.click(screen.getByRole('button',{name:'Save'}))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({capital_structure_date:'2026-07-31',capital_structure_value:'250000',capital_structure_debt:null},expect.anything()))
})
