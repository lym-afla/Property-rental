import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TransactionForm } from './TransactionForm'
import { fixtureProperty, fixturePropertyAlt } from '@/__fixtures__/property'
import { fixtureTenant } from '@/__fixtures__/tenant'

const properties = [fixtureProperty, { ...fixturePropertyAlt, currency: 'GBP' }]
const tenants = [
  { ...fixtureTenant, id: 1, first_name: 'Former', lease_end: '2026-10-31' },
  { ...fixtureTenant, id: 2, first_name: 'Current', lease_end: null },
  { ...fixtureTenant, id: 3, first_name: 'Today', lease_end: '2026-11-01' },
  { ...fixtureTenant, id: 4, first_name: 'Future', lease_end: '2027-01-01' },
  { ...fixtureTenant, id: 5, first_name: 'Other', property: 2, lease_end: null },
]
const values = { property: 1, date: '2026-11-01', amount: '100', category: 'rent' as const }

async function select(label: string, option: string) {
  const user = userEvent.setup()
  await user.click(screen.getByRole('combobox', { name: label }))
  await user.click(screen.getByRole('option', { name: option }))
}

describe('TransactionForm', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-11-01T12:00:00Z'))
  })
  afterEach(() => vi.useRealTimers())

  it('defaults to each selected property currency and keeps manual overrides on refetch', async () => {
    const props = { properties, tenants, onSubmit: vi.fn() }
    const { rerender } = render(<TransactionForm {...props} />)
    expect(screen.getByRole('combobox', { name: 'Tenant (optional)' })).toBeDisabled()
    await select('Property', 'Riverside Flat')
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('EUR')
    await select('Currency', 'USD')
    rerender(<TransactionForm {...props} properties={[...properties]} />)
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2024-01-01' } })
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('USD')
    await select('Property', 'Lakeside House')
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('GBP')
  })

  it('initializes currency when preselected property data arrives', async () => {
    const props = { tenants, defaultValues: values, onSubmit: vi.fn() }
    const { rerender } = render(<TransactionForm {...props} properties={[]} />)
    rerender(<TransactionForm {...props} properties={properties} />)
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('EUR'))
    await select('Currency', 'USD')
    rerender(<TransactionForm {...props} properties={[...properties]} />)
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('USD')
  })

  it('does not replace a manual currency chosen before property data arrives', async () => {
    const props = { tenants, defaultValues: values, onSubmit: vi.fn() }
    const { rerender } = render(<TransactionForm {...props} properties={[]} />)
    await select('Currency', 'GBP')
    rerender(<TransactionForm {...props} properties={properties} />)
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('GBP')
  })

  it('retains an explicit return to USD before property data arrives', async () => {
    const props = { tenants, defaultValues: values, onSubmit: vi.fn() }
    const { rerender } = render(<TransactionForm {...props} properties={[]} />)
    await select('Currency', 'GBP')
    await select('Currency', 'USD')
    rerender(<TransactionForm {...props} properties={properties} />)
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('USD')
  })

  it('waits for an assigned tenant before allowing it to be hidden', () => {
    const props = { mode: 'edit' as const, properties, defaultValues: { ...values, tenant: 1 }, onSubmit: vi.fn() }
    const { rerender } = render(<TransactionForm {...props} tenants={[]} />)
    expect(screen.getByRole('checkbox', { name: 'Show former tenants' })).toBeDisabled()
    rerender(<TransactionForm {...props} tenants={tenants} />)
    expect(screen.getByRole('checkbox', { name: 'Show former tenants' })).toBeEnabled()
    expect(screen.getByRole('checkbox', { name: 'Show former tenants' })).toBeChecked()
    expect(screen.getByRole('combobox', { name: 'Tenant (optional)' })).toHaveTextContent('Former Jones')
  })

  it('shows non-vacated tenants by default regardless of transaction date', async () => {
    render(<TransactionForm properties={properties} tenants={tenants} defaultValues={values} onSubmit={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2024-01-01' } })
    const user = userEvent.setup()
    await user.click(screen.getByRole('combobox', { name: 'Tenant (optional)' }))
    expect(screen.getByRole('option', { name: 'Current Jones' })).toBeVisible()
    expect(screen.getByRole('option', { name: 'Today Jones' })).toBeVisible()
    expect(screen.getByRole('option', { name: 'Future Jones' })).toBeVisible()
    expect(screen.queryByRole('option', { name: /Former/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Other/ })).not.toBeInTheDocument()
    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('checkbox', { name: 'Show former tenants' }))
    await user.click(screen.getByRole('combobox', { name: 'Tenant (optional)' }))
    expect(screen.getAllByRole('option').map(o => o.textContent)).toEqual([
      'Unassigned', 'Current Jones', 'Today Jones', 'Future Jones', 'Former Jones · Former tenant',
    ])
  })

  it('clears a selected former tenant when hidden and submits an unassigned transaction', async () => {
    const onSubmit = vi.fn()
    render(<TransactionForm properties={properties} tenants={tenants} defaultValues={values} onSubmit={onSubmit} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('checkbox', { name: 'Show former tenants' }))
    await select('Tenant (optional)', 'Former Jones · Former tenant')
    await user.click(screen.getByRole('checkbox', { name: 'Show former tenants' }))
    expect(screen.getByRole('combobox', { name: 'Tenant (optional)' })).toHaveTextContent('Unassigned')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ tenant: null, currency: 'EUR' })
  })

  it('clears mismatched tenants on property change and offers explicit unassignment', async () => {
    render(<TransactionForm properties={properties} tenants={tenants} defaultValues={values} onSubmit={vi.fn()} />)
    await select('Tenant (optional)', 'Current Jones')
    await select('Property', 'Lakeside House')
    expect(screen.getByRole('combobox', { name: 'Tenant (optional)' })).toHaveTextContent('Unassigned')
    await select('Tenant (optional)', 'Other Jones')
    await select('Tenant (optional)', 'Unassigned')
    expect(screen.getByRole('combobox', { name: 'Tenant (optional)' })).toHaveTextContent('Unassigned')
  })

  it('retains historical currency, former tenant and custom period on edit with delayed data', async () => {
    const onSubmit = vi.fn()
    const props = { mode: 'edit' as const, defaultValues: { ...values, tenant: 1, currency: 'USD' as const, period: '2026-09' }, onSubmit }
    const { rerender } = render(<TransactionForm {...props} properties={[]} tenants={[]} />)
    rerender(<TransactionForm {...props} properties={properties} tenants={tenants} />)
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('USD')
    expect(screen.getByRole('checkbox', { name: 'Show former tenants' })).toBeChecked()
    expect(screen.getByRole('combobox', { name: 'Tenant (optional)' })).toHaveTextContent('Former Jones')
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ tenant: 1, currency: 'USD', period: '2026-09' })
    await select('Property', 'Lakeside House')
    expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveTextContent('GBP')
    expect(screen.getByRole('combobox', { name: 'Tenant (optional)' })).toHaveTextContent('Unassigned')
  })
})
