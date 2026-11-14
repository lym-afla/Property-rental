import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { LoanPayment } from '@/types/loan'

export function LoanPaymentForm({ onSubmit, isSubmitting }: { onSubmit: (data: LoanPayment) => void; isSubmitting?: boolean }) {
  const [mode, setMode] = useState('total')
  const [error, setError] = useState('')
  return <form className="space-y-4" onSubmit={(event) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const interest = String(data.get('interest'))
    const amount = String(data.get(mode))
    if (!/^\d+(\.\d{1,2})?$/.test(interest) || !/^\d+(\.\d{1,2})?$/.test(amount)) {
      setError('Enter non-negative amounts with at most two decimal places.'); return
    }
    if (mode === 'total' && Number(amount) < Number(interest)) {
      setError('Total must be at least the interest'); return
    }
    if (Number(amount) + (mode === 'principal' ? Number(interest) : 0) <= 0) {
      setError('Payment must be greater than zero.'); return
    }
    setError('')
    onSubmit({ date: String(data.get('date')), interest, [mode]: amount, comment: String(data.get('comment')) })
  }}>
    <label className="block space-y-1">Payment date<Input name="date" type="date" required /></label>
    <label className="block space-y-1">Enter payment as<select className="block min-h-11 w-full rounded-md border bg-background px-3" value={mode} onChange={(e) => { setMode(e.target.value); setError('') }}>
      <option value="total">Total + interest</option><option value="principal">Interest + principal</option>
    </select></label>
    <label className="block space-y-1">Interest<Input name="interest" inputMode="decimal" required /></label>
    <label className="block space-y-1">{mode === 'total' ? 'Total payment' : 'Principal'}<Input key={mode} name={mode} inputMode="decimal" required /></label>
    <label className="block space-y-1">Comment<Input name="comment" /></label>
    <p className="text-sm text-muted-foreground">Interest counts as a cost. Principal reduces the loan balance and does not affect profit.</p>
    {error && <p role="alert" className="text-destructive">{error}</p>}
    <Button type="submit" disabled={isSubmitting}>Save payment</Button>
  </form>
}
