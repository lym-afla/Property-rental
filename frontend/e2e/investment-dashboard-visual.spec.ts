import { expect, test } from '@playwright/test'

test('dashboard visual baseline stays legible at each required viewport', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    if (path.endsWith('/auth/csrf/')) return json({})
    if (path.endsWith('/auth/me/')) return json({ user: { id: 1, username: 'visual', email: 'visual@example.test', first_name: 'Visual', last_name: 'QA', is_landlord: true, is_tenant: false, effective_date: '2024-02-29', default_currency: 'USD', use_default_currency_for_all_data: false, chart_frequency: 'M', chart_timeline: '6m', digits: 0 } })
    if (path.endsWith('/properties/')) return json([])
    if (path.includes('/analytics/portfolio/summary/')) return json({ currency: 'USD', scale: 1, start: '2024-01-01', end: '2024-02-29', property_count: 0, rental_inventory_count: 0, occupied: 0, occupancy_rate: 0, revenue: 0, costs: 0, net_income: 0, property_value: null, debt: null, equity: null, valuation_status: 'missing_valuation', property_value_status: 'missing_valuation', debt_status: 'missing_valuation' })
    if (path.includes('/analytics/')) return json({ metric: path.includes('occupancy') ? 'portfolio_occupancy' : 'portfolio_cash_flow', grain: 'month', currency: path.includes('occupancy') ? null : 'USD', scale: 1, start: '2024-01-01', end: '2024-02-29', series: [], points: [] })
    return json([])
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Investment dashboard' })).toBeVisible()
  await expect(page).toHaveScreenshot('investment-dashboard-empty.png', { fullPage: true, animations: 'disabled' })
})
