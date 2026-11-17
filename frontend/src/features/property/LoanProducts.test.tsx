import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import { server } from '@/test/handlers'
import type { Loan, LoanProduct } from '@/types/loan'
import { LoanProducts } from './LoanProducts'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const loan: Loan = { id: 9, property: 1, lender: 'Current bank', currency: 'GBP', reference: '', start_date: '2025-04-01', end_date: null, original_principal: null, interest_rate: '4.09', rate_type: 'fixed', created_at: '', updated_at: '' }
const early: LoanProduct = { id: 1, loan: 9, name: 'Earlier tracker', lender: 'Earlier bank', start_date: '2017-04-01', end_date: '2019-02-28', interest_rate: '2.49', rate_type: 'variable', opening_balance: '200000', notes: 'Initial rate from the offer; later changes estimated.', created_at: '', updated_at: '' }
const current: LoanProduct = { ...early, id: 2, name: 'Current fix', lender: 'Current bank', start_date: '2025-04-01', end_date: null, interest_rate: '4.09', rate_type: 'fixed', opening_balance: null, notes: '' }
function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><LoanProducts loan={loan} /></QueryClientProvider>)
}
it('shows distinct products in date order with lenders, initial rates and uncertainty', async () => {
  server.use(http.get('/api/v1/loan-products/', ({ request }) => {
    expect(new URL(request.url).searchParams.get('loan')).toBe('9')
    return HttpResponse.json([current, early, { ...early, id: 3, name: 'Original mortgage', start_date: '2012-08-15', interest_rate: null, rate_type: '', opening_balance: null }])
  }))
  show()
  expect(await screen.findByText('Earlier tracker')).toBeInTheDocument()
  const rows = screen.getAllByRole('listitem')
  expect(rows.map((row) => within(row).getByRole('heading').textContent)).toEqual(['Original mortgage', 'Earlier tracker', 'Current fix'])
  expect(within(rows[0]).getByText('Initial rate unknown')).toBeInTheDocument()
  expect(within(rows[1]).getByText(/2.49% variable/)).toBeInTheDocument()
  expect(within(rows[2]).getByText(/4.09% fixed/)).toBeInTheDocument()
  expect(within(rows[1]).getByText(/Opening balance: £200,000/)).toBeInTheDocument()
  expect(within(rows[1]).getByText(early.notes)).toBeInTheDocument()
})
it('creates and edits a product, refreshes the list, and confirms deletion', async () => {
  let products: LoanProduct[] = []
  const deletion = vi.fn()
  server.use(
    http.get('/api/v1/loan-products/', () => HttpResponse.json(products)),
    http.post('/api/v1/loan-products/', async ({ request }) => {
      const body = await request.json()
      expect(body).toEqual({ loan: 9, name: 'New fix', lender: 'Another bank', start_date: '2027-04-01', end_date: '2029-03-31', interest_rate: '3.5', rate_type: 'fixed', opening_balance: null, notes: 'Offer estimate' })
      products = [{ ...current, ...body as object, id: 3 }]
      return HttpResponse.json(products[0], { status: 201 })
    }),
    http.patch('/api/v1/loan-products/3/', async ({ request }) => {
      products = [{ ...products[0], ...await request.json() as object }]
      return HttpResponse.json(products[0])
    }),
    http.delete('/api/v1/loan-products/3/', () => { deletion(); products = []; return new HttpResponse(null, { status: 204 }) }),
  )
  const user = userEvent.setup()
  show()
  await user.click(screen.getByRole('button', { name: 'Add mortgage product' }))
  await user.type(screen.getByLabelText('Product name'), 'New fix')
  await user.clear(screen.getByLabelText('Lender'))
  await user.type(screen.getByLabelText('Lender'), 'Another bank')
  await user.type(screen.getByLabelText('Start date'), '2027-04-01')
  await user.type(screen.getByLabelText('End date (optional)'), '2029-03-31')
  await user.type(screen.getByLabelText('Initial interest rate % (optional)'), '3.5')
  await user.selectOptions(screen.getByLabelText('Rate type'), 'fixed')
  await user.type(screen.getByLabelText('Source and uncertainty notes (optional)'), 'Offer estimate')
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('New fix')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Edit product' }))
  await user.clear(screen.getByLabelText('Product name'))
  await user.type(screen.getByLabelText('Product name'), 'Updated fix')
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  expect(await screen.findByText('Updated fix')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Delete product' }))
  expect(deletion).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(deletion).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Delete product' }))
  await user.click(screen.getByRole('button', { name: 'Confirm delete product' }))
  await waitFor(() => expect(screen.queryByText('Updated fix')).not.toBeInTheDocument())
  expect(deletion).toHaveBeenCalledOnce()
})
it('keeps entered values and displays a server validation error without closing the form', async () => {
  server.use(
    http.get('/api/v1/loan-products/', () => HttpResponse.json([current])),
    http.patch('/api/v1/loan-products/2/', () => HttpResponse.json({ start_date: ['Product dates overlap an existing product.'] }, { status: 400 })),
  )
  const user = userEvent.setup()
  show()
  await user.click(await screen.findByRole('button', { name: 'Edit product' }))
  await user.click(screen.getByRole('button', { name: 'Save product' }))
  await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Product dates overlap an existing product.'))
  expect(screen.getByLabelText('Product name')).toHaveValue('Current fix')
  expect(screen.getByLabelText('Initial interest rate % (optional)')).toHaveAttribute('min', '0')
  expect(screen.getByLabelText('Source and uncertainty notes (optional)')).toHaveAttribute('maxlength', '2000')
})
it('shows product loading failures with a retry action', async () => {
  let failed = true
  server.use(http.get('/api/v1/loan-products/', () => failed ? HttpResponse.json({}, { status: 500 }) : HttpResponse.json([current])))
  const user = userEvent.setup()
  show()
  expect(await screen.findByText('Failed to load mortgage products')).toBeInTheDocument()
  failed = false
  await user.click(screen.getByRole('button', { name: /retry/i }))
  expect(await screen.findByText('Current fix')).toBeInTheDocument()
})
