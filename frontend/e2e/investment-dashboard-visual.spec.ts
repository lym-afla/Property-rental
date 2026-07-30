import { expect, test } from '@playwright/test'

test.skip(process.platform !== 'win32' || process.env.PW_CHANNEL !== 'chrome', 'Visual baselines are pinned to Windows Chrome.')

test('populated dashboard visual baseline preserves chart layout and exact values at each required viewport', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    if (path.endsWith('/auth/csrf/')) return json({})
    if (path.endsWith('/auth/me/')) return json({ user: { id: 1, username: 'visual', email: 'visual@example.test', first_name: 'Visual', last_name: 'QA', is_landlord: true, is_tenant: false, effective_date: '2024-02-29', default_currency: 'USD', use_default_currency_for_all_data: false, chart_frequency: 'M', chart_timeline: '6m', digits: 0 } })
    if (path.endsWith('/properties/')) return json([{ id: 1, owned_by: 1, name: 'Long Riverside apartment label for visual overflow coverage', location: 'Berlin', address: '1 Test Street', num_bedrooms: 2, area: '70', currency: 'EUR', sold: null }, { id: 2, owned_by: 1, name: 'Dollar House', location: 'New York', address: '2 Test Street', num_bedrooms: 1, area: '45', currency: 'USD', sold: null }])
    const range = { start: '2024-01-01', end: '2024-02-29' }
    const january = { period_start: '2024-01-01', period_end: '2024-01-31' }
    const february = { period_start: '2024-02-01', period_end: '2024-02-29' }
    if (path.includes('/analytics/portfolio/summary/')) return json({ currency: 'USD', scale: 1, ...range, property_count: 2, rental_inventory_count: 2, occupied: 2, occupancy_rate: 100, revenue: 2000, costs: 350, net_income: 1650, property_value: 400000, debt: 100000, equity: 300000, valuation_status: 'ok', property_value_status: 'ok', debt_status: 'ok' })
    if (path.includes('/analytics/portfolio/cash-flow/')) return json({ metric: 'portfolio_cash_flow', grain: 'month', currency: 'USD', scale: 1, ...range, series: [{ key: 'rent', label: 'Rent income', kind: 'income_category' }, { key: 'repairs', label: 'Repairs', kind: 'expense_category' }, { key: 'total_income', label: 'Total income', kind: 'income_total' }, { key: 'total_expenses', label: 'Total expenses', kind: 'expense_total' }, { key: 'net_income', label: 'Net income', kind: 'net' }, { key: 'cumulative_net_income', label: 'Cumulative net income', kind: 'cumulative' }], points: [{ ...january, rent: 2000, repairs: -350, total_income: 2000, total_expenses: -350, net_income: 1650, cumulative_net_income: 1650 }, { ...february, rent: 2200, repairs: -500, total_income: 2200, total_expenses: -500, net_income: 1700, cumulative_net_income: 3350 }] })
    if (path.includes('/analytics/portfolio/expenses/')) return json({ metric: 'expense_drivers', grain: 'month', currency: 'USD', scale: 1, ...range, series: [{ key: 'repairs', label: 'Repairs', kind: 'expense_category' }], points: [{ ...january, repairs: -350 }, { ...february, repairs: -500 }] })
    if (path.includes('/analytics/portfolio/property-contribution/')) return json({ metric: 'property_contribution', currency: 'USD', scale: 1, ...range, portfolio_net_income: 1650, rows: [{ property_id: 1, property_name: 'Long Riverside apartment label for visual overflow coverage', revenue: 1000, costs: 400, net_income: 600, portfolio_share: 36.4 }, { property_id: 2, property_name: 'Dollar House (negative contributor)', revenue: 1000, costs: 950, net_income: -50, portfolio_share: -3 }] })
    if (path.includes('/analytics/portfolio/yields/')) return json({ metric: 'property_yields', currency: 'USD', scale: 1, ...range, rows: [{ property_id: 1, property_name: 'Long Riverside apartment label for visual overflow coverage', valuation_date: range.end, property_value: 250000, debt: 100000, equity: 150000, annualized_revenue: 12000, annualized_costs: 4800, gross_yield: 4.8, equity_yield: 4.8, status: 'ok' }] })
    if (path.includes('/analytics/portfolio/property-breakdown/')) return json({ metric: 'property_breakdown', grain: 'month', currency: 'USD', scale: 1, ...range, measure: 'property_value', measure_label: 'Property value', series: [{ key: 'property_1', label: 'Long Riverside apartment label for visual overflow coverage', kind: 'property' }, { key: 'property_2', label: 'Dollar House', kind: 'property' }], points: [{ ...january, property_1: 250000, property_2: 150000 }, { ...february, property_1: 255000, property_2: 152000 }], coverage: [{ ...january, property_id: 1, status: 'ok' }, { ...january, property_id: 2, status: 'ok' }, { ...february, property_id: 1, status: 'ok' }, { ...february, property_id: 2, status: 'ok' }] })
    if (path.includes('/analytics/portfolio/occupancy/')) return json({ metric: 'portfolio_occupancy', grain: 'month', currency: null, scale: 1, ...range, series: [{ key: 'capacity', label: 'Capacity', kind: 'capacity' }, { key: 'occupied', label: 'Occupied', kind: 'occupied' }, { key: 'vacant', label: 'Vacant', kind: 'vacant' }, { key: 'occupancy_rate', label: 'Occupancy rate', kind: 'percentage' }], points: [{ ...january, capacity: 2, occupied: 2, vacant: 0, occupancy_rate: 100 }, { ...february, capacity: 2, occupied: 1, vacant: 1, occupancy_rate: 50 }] })
    return json([])
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Investment dashboard' })).toBeVisible()
  await expect(page.getByText('Net cash flow', { exact: true })).toBeVisible()
  await expect(page.getByText('Cumulative cash', { exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  // Screenshot stabilization fast-forwards finite Recharts animations before
  // the geometry assertions inspect the final plotted SVG marks.
  await expect(page).toHaveScreenshot('investment-dashboard-populated.png', { fullPage: true, animations: 'disabled' })

  const cashFlowCard = page.getByText('Net cash flow', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  const zeroLine = cashFlowCard.locator('.recharts-reference-line-line')
  const incomeBar = cashFlowCard.locator('.recharts-bar-rectangle path[fill="url(#cash-flow-primary)"]').first()
  const expenseBar = cashFlowCard.locator('.recharts-bar-rectangle path[fill="url(#cash-flow-secondary)"]').first()
  const [zeroBox, incomeBox, expenseBox] = await Promise.all([zeroLine.boundingBox(), incomeBar.boundingBox(), expenseBar.boundingBox()])
  expect(zeroBox).not.toBeNull()
  expect(incomeBox).not.toBeNull()
  expect(expenseBox).not.toBeNull()
  // Recharts centers the two-pixel bar stroke on the zero baseline and rounds
  // the SVG geometry to half pixels, so allow only that small shared edge.
  expect((incomeBox?.y ?? Infinity) + (incomeBox?.height ?? 0)).toBeLessThanOrEqual((zeroBox?.y ?? -Infinity) + 3)
  expect(expenseBox?.y ?? -Infinity).toBeGreaterThanOrEqual((zeroBox?.y ?? Infinity) - 3)
  expect((expenseBox?.y ?? 0) + (expenseBox?.height ?? 0)).toBeGreaterThan(zeroBox?.y ?? Infinity)

  await page.getByRole('button', { name: 'Table' }).first().click()
  await expect(page.getByRole('table', { name: 'Net cash flow exact values' })).toBeVisible()
  await expect(page).toHaveScreenshot('investment-dashboard-populated-table.png', { fullPage: true, animations: 'disabled' })
})
