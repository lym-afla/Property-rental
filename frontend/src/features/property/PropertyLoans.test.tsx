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
