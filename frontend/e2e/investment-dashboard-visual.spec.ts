import { expect, test } from '@playwright/test'

test('populated dashboard visual baseline preserves chart layout and exact values at each required viewport', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    if (path.endsWith('/auth/csrf/')) return json({})
    if (path.endsWith('/auth/me/')) return json({ user: { id: 1, username: 'visual', email: 'visual@example.test', first_name: 'Visual', last_name: 'QA', is_landlord: true, is_tenant: false, effective_date: '2024-02-29', default_currency: 'USD', use_default_currency_for_all_data: false, chart_frequency: 'M', chart_timeline: '6m', digits: 0 } })
    if (path.endsWith('/properties/')) return json([{ id: 1, owned_by: 1, name: 'Long Riverside apartment label for visual overflow coverage', location: 'Berlin', address: '1 Test Street', num_bedrooms: 2, area: '70', currency: 'EUR', sold: null }, { id: 2, owned_by: 1, name: 'Dollar House', location: 'New York', address: '2 Test Street', num_bedrooms: 1, area: '45', currency: 'USD', sold: null }])
    const range = { start: '2024-01-01', end: '2024-02-29' }
    const period = { period_start: range.start, period_end: range.end }
    if (path.includes('/analytics/portfolio/summary/')) return json({ currency: 'USD', scale: 1, ...range, property_count: 2, rental_inventory_count: 2, occupied: 2, occupancy_rate: 100, revenue: 2000, costs: 350, net_income: 1650, property_value: 400000, debt: 100000, equity: 300000, valuation_status: 'ok', property_value_status: 'ok', debt_status: 'ok' })
    if (path.includes('/analytics/portfolio/cash-flow/')) return json({ metric: 'portfolio_cash_flow', grain: 'month', currency: 'USD', scale: 1, ...range, series: [{ key: 'rent', label: 'Rent income', kind: 'income_category' }, { key: 'repairs', label: 'Repairs', kind: 'expense_category' }], points: [{ ...period, rent: 2000, repairs: -350 }] })
    if (path.includes('/analytics/portfolio/expenses/')) return json({ metric: 'expense_drivers', grain: 'month', currency: 'USD', scale: 1, ...range, series: [{ key: 'repairs', label: 'Repairs', kind: 'expense_category' }], points: [{ ...period, repairs: -350 }] })
    if (path.includes('/analytics/portfolio/property-contribution/')) return json({ metric: 'property_contribution', currency: 'USD', scale: 1, ...range, portfolio_net_income: 1650, rows: [{ property_id: 1, property_name: 'Long Riverside apartment label for visual overflow coverage', revenue: 1000, costs: 400, net_income: 600, portfolio_share: 36.4 }, { property_id: 2, property_name: 'Dollar House (negative contributor)', revenue: 1000, costs: 950, net_income: -50, portfolio_share: -3 }] })
    if (path.includes('/analytics/portfolio/yields/')) return json({ metric: 'property_yields', currency: 'USD', scale: 1, ...range, rows: [{ property_id: 1, property_name: 'Long Riverside apartment label for visual overflow coverage', valuation_date: range.end, property_value: 250000, annualized_revenue: 12000, annualized_costs: 4800, gross_yield: 4.8, net_yield: 2.88, status: 'ok' }] })
    if (path.includes('/analytics/portfolio/currency-exposure/')) return json({ metric: 'currency_exposure', grain: 'month', currency: 'USD', scale: 1, ...range, measure: 'property_value', measure_label: 'Property value', series: [{ key: 'eur', label: 'EUR', kind: 'currency' }, { key: 'usd', label: 'USD', kind: 'currency' }], points: [{ ...period, eur: 250000, usd: 150000 }], coverage: [{ ...period, currency: 'USD', status: 'ok', missing_count: 0, stale_count: 0 }] })
    if (path.includes('/analytics/portfolio/occupancy/')) return json({ metric: 'portfolio_occupancy', grain: 'month', currency: null, scale: 1, ...range, series: [{ key: 'occupancy_rate', label: 'Occupancy rate', kind: 'occupancy' }], points: [{ ...period, occupancy_rate: 100, occupied: 2, vacant: 0, capacity: 2 }] })
    return json([])
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Investment dashboard' })).toBeVisible()
  await expect(page.getByText('Dollar House (negative contributor)')).toBeVisible()
  await expect(page.getByRole('button', { name: 'EUR' })).toBeVisible()
  await expect(page).toHaveScreenshot('investment-dashboard-populated.png', { fullPage: true, animations: 'disabled' })
})
