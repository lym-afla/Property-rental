import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { FinancialDefinitions } from './FinancialDefinitions'

describe('FinancialDefinitions', () => {
  it('opens from the keyboard and returns focus after dismissal', async () => {
    const user = userEvent.setup()
    render(<FinancialDefinitions />)
    const trigger = screen.getByRole('button', { name: 'Yield definitions' })

    expect(trigger).toHaveClass('min-h-11', 'min-w-11')
    trigger.focus()
    await user.keyboard('{Enter}')

    expect(screen.getByRole('dialog', { name: 'Yield definitions' })).toBeVisible()
    expect(screen.getByText('Gross yield — annualized gross rental income divided by the latest property value.')).toBeVisible()
    expect(screen.getByText('Equity yield — annualized rental income net of costs divided by equity.')).toBeVisible()
    expect(screen.getByText('Equity — latest property value less latest debt, using records available as of the selected date.')).toBeVisible()

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })
})
