import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { SecurityDepositCard } from './SecurityDepositCard'
import type { DepositMovement } from '@/types/deposit'

const mocks = vi.hoisted(() => ({
  movements: { data: [] as DepositMovement[], isLoading: false, isError: false },
  balance: {
    data: undefined as
      | { as_of: string; balances: { currency: string; amount: string }[] }
      | undefined,
  },
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}))

vi.mock('@/api/deposits', () => ({
  useDepositMovements: () => mocks.movements,
  useDepositBalance: () => mocks.balance,
  useCreateDepositMovement: () => ({ mutateAsync: mocks.create }),
  useUpdateDepositMovement: () => ({ mutateAsync: mocks.update }),
  useDeleteDepositMovement: () => ({ mutateAsync: mocks.remove, isPending: false }),
}))

const received: DepositMovement = {
  id: 7,
  tenant: 1,
  date: '2024-01-05',
  kind: 'received',
  currency: 'EUR',
  amount: '1000.00',
  applied_to: null,
  transaction: null,
  owns_transaction: false,
  comment: 'Initial deposit',
}
const applied: DepositMovement = {
  ...received,
  id: 8,
  date: '2024-02-05',
  kind: 'applied',
  amount: '200.00',
  applied_to: 'rent',
  comment: null,
}

function renderCard() {
  return render(
    <SecurityDepositCard
      tenantId={1}
      propertyCurrency="EUR"
      asOf="2024-03-01"
      transactions={[]}
    />,
  )
}

beforeEach(() => {
  mocks.movements = { data: [received, applied], isLoading: false, isError: false }
  mocks.balance = {
    data: { as_of: '2024-03-01', balances: [{ currency: 'EUR', amount: '800.00' }] },
  }
  mocks.create.mockReset()
  mocks.update.mockReset()
  mocks.remove.mockReset()
})

describe('SecurityDepositCard', () => {
  it('renders the held balance and the movements', () => {
    renderCard()
    expect(screen.getByText('Security deposit')).toBeInTheDocument()
    expect(screen.getByText('Held')).toBeInTheDocument()
    expect(screen.getByText('€800')).toBeInTheDocument()
    expect(screen.getByText('Initial deposit')).toBeInTheDocument()
    expect(screen.getByText('Received')).toBeInTheDocument()
    expect(screen.getByText('Applied')).toBeInTheDocument()
    expect(screen.getByText('Rent')).toBeInTheDocument()
  })

  it('shows None held when there are no balances', () => {
    mocks.balance = { data: { as_of: '2024-03-01', balances: [] } }
    mocks.movements = { data: [], isLoading: false, isError: false }
    renderCard()
    expect(screen.getByText('None held')).toBeInTheDocument()
  })

  it('opens the create dialog from Add', async () => {
    const user = userEvent.setup()
    renderCard()
    await user.click(screen.getByRole('button', { name: /add/i }))
    expect(
      await screen.findByText('New Security deposit movement'),
    ).toBeInTheDocument()
  })

  it('opens the edit dialog from Edit', async () => {
    const user = userEvent.setup()
    renderCard()
    await user.click(screen.getAllByRole('button', { name: 'Edit' })[0])
    expect(
      await screen.findByText('Edit Security deposit movement'),
    ).toBeInTheDocument()
  })

  it('confirms before deleting a movement', async () => {
    const user = userEvent.setup()
    mocks.remove.mockResolvedValue(undefined)
    renderCard()
    await user.click(screen.getAllByRole('button', { name: 'Delete' })[0])
    expect(mocks.remove).not.toHaveBeenCalled()
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith(7))
  })
})
