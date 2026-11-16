import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, it } from 'vitest'
import { server } from '@/test/handlers'
import { PropertyLoans } from './PropertyLoans'

const loan = { id: 9, property: 1, lender: 'UNKNOWN — fill in', currency: 'GBP', reference: 'M123', start_date: '2020-01-01', end_date: null, original_principal: null, interest_rate: null, rate_type: '' }

it('shows reconciliation discrepancies and lets the user replace a migrated lender', async () => {
  let lender = loan.lender
  server.use(
    http.get('/api/v1/loans/', () => HttpResponse.json([{ ...loan, lender }])),
    http.get('/api/v1/loans/9/reconciliation/', () => HttpResponse.json([{opening_date: '2026-01-01', closing_date:'2026-02-01', expected_closing_debt:'99000', closing_debt:'99500', difference:'500', flagged:true}])),
    http.patch('/api/v1/loans/9/', async ({ request }) => {
      const body = await request.json() as { lender: string }
      lender = body.lender
      return HttpResponse.json({ ...loan, lender })
    }),
  )
  const user = userEvent.setup()
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><PropertyLoans property={1} currency="GBP" /></QueryClientProvider>)
  expect(await screen.findByText(/Fill in the lender/)).toBeInTheDocument()
  expect(await screen.findByText(/Balance mismatch/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', {name:'Edit loan'}))
  await user.clear(screen.getByLabelText('Lender'))
  await user.type(screen.getByLabelText('Lender'), 'Example Bank')
  await user.click(screen.getByRole('button', {name:'Save loan'}))
  await waitFor(() => expect(screen.getByRole('heading', {name:'Example Bank'})).toBeInTheDocument())
  expect(screen.queryByText(/Fill in the lender/)).not.toBeInTheDocument()
})

it('records a capitalised fee separately from payments and includes it in balance checks', async () => {
  let fees: { id: number; loan: number; date: string; amount: string; description: string }[] = []
  server.use(
    http.get('/api/v1/loans/', () => HttpResponse.json([loan])),
    http.get('/api/v1/loan-capitalised-fees/', ({ request }) => {
      expect(new URL(request.url).searchParams.get('loan')).toBe('9')
      return HttpResponse.json(fees)
    }),
    http.get('/api/v1/loans/9/reconciliation/', () => HttpResponse.json([{
      opening_date: '2025-03-31', closing_date: '2025-04-30', expected_closing_debt: fees.length ? '100499' : '99500',
      closing_debt: '100499', difference: fees.length ? '0' : '999', flagged: !fees.length, capitalised_fees: fees.length ? '999.00' : '0.00',
    }])),
    http.post('/api/v1/loan-capitalised-fees/', async ({ request }) => {
      const body = await request.json() as Omit<typeof fees[number], 'id'>
      expect(body).toEqual({ loan: 9, date: '2025-04-01', amount: '999', description: 'Product switch fee' })
      fees = [{ ...body, id: 3 }]
      return HttpResponse.json(fees[0], { status: 201 })
    }),
    http.patch('/api/v1/loan-capitalised-fees/3/', async ({ request }) => {
      const body = await request.json() as Partial<typeof fees[number]>
      fees = [{ ...fees[0], ...body }]
      return HttpResponse.json(fees[0])
    }),
    http.delete('/api/v1/loan-capitalised-fees/3/', () => {
      fees = []
      return new HttpResponse(null, { status: 204 })
    }),
  )
  const user = userEvent.setup()
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><PropertyLoans property={1} currency="GBP" /></QueryClientProvider>)
  expect(await screen.findByText(/Balance mismatch/)).toBeInTheDocument()
  await user.click(await screen.findByRole('button', { name: 'Add capitalised fee' }))
  expect(screen.getByText(/Added to the loan balance/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('Fee date'), '2025-04-01')
  await user.type(screen.getByLabelText('Fee amount'), '999')
  await user.type(screen.getByLabelText('Description (optional)'), 'Product switch fee')
  await user.click(screen.getByRole('button', { name: 'Save fee' }))
  expect(await screen.findByText('Product switch fee')).toBeInTheDocument()
  expect(await screen.findByText(/Recorded debt balances agree/)).toBeInTheDocument()
  expect(screen.getByText(/Includes £999 in capitalised fees/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Edit fee' }))
  await user.clear(screen.getByLabelText('Description (optional)'))
  await user.type(screen.getByLabelText('Description (optional)'), 'Nationwide fee')
  await user.click(screen.getByRole('button', { name: 'Save fee' }))
  expect(await screen.findByText('Nationwide fee')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Delete fee' }))
  await user.click(screen.getByRole('button', { name: 'Confirm delete fee' }))
  await waitFor(() => expect(screen.queryByText('Nationwide fee')).not.toBeInTheDocument())
  expect(await screen.findByText(/Balance mismatch/)).toBeInTheDocument()
})

it('keeps a mismatch visible when capitalised fees do not explain the whole difference', async () => {
  server.use(
    http.get('/api/v1/loans/', () => HttpResponse.json([loan])),
    http.get('/api/v1/loan-capitalised-fees/', () => HttpResponse.json([{ id: 3, loan: 9, date: '2025-04-01', amount: '999.00', description: 'Product fee' }])),
    http.get('/api/v1/loans/9/reconciliation/', () => HttpResponse.json([{
      opening_date: '2025-03-31', closing_date: '2025-04-30', expected_closing_debt: '100499',
      closing_debt: '100699', difference: '200', flagged: true, capitalised_fees: '999.00',
    }])),
  )
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><PropertyLoans property={1} currency="GBP" /></QueryClientProvider>)
  expect(await screen.findByText(/Balance mismatch.*difference £200/)).toBeInTheDocument()
  expect(screen.getByText(/Includes £999 in capitalised fees/)).toBeInTheDocument()
  expect(screen.queryByText(/Recorded debt balances agree/)).not.toBeInTheDocument()
})
