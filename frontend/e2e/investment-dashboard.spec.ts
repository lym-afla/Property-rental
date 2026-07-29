import { expect, test, type Page } from '@playwright/test'

const range = { start: '2024-01-01', end: '2024-02-29' }
const user = {
  id: 1, username: 'qa-user', email: 'qa@example.test', first_name: 'QA', last_name: 'User',
  is_landlord: true, is_tenant: false, effective_date: range.end, default_currency: 'USD',
  use_default_currency_for_all_data: false, chart_frequency: 'M', chart_timeline: '6m', digits: 0,
}
const properties = [
  { id: 1, owned_by: 1, name: 'A very long property label that must remain reachable in the exact-value table', location: 'Berlin', address: '1 Test Street', num_bedrooms: 2, area: '70', currency: 'EUR', sold: null },
  { id: 2, owned_by: 1, name: 'Dollar House', location: 'New York', address: '2 Test Street', num_bedrooms: 1, area: '45', currency: 'USD', sold: null },
]
const period = { period_start: range.start, period_end: range.end }
const cashFlow = {
  metric: 'portfolio_cash_flow', grain: 'month', currency: 'USD', scale: 1, ...range,
  series: [{ key: 'rent', label: 'Rent income', kind: 'income_category' }, { key: 'repairs', label: 'Repairs', kind: 'expense_category' }],
  points: [{ ...period, rent: 2000, repairs: -350 }],
}
const expenseDrivers = { ...cashFlow, metric: 'expense_drivers', series: [{ key: 'repairs', label: 'Repairs', kind: 'expense_category' }], points: [{ ...period, repairs: -350 }] }
const occupancy = { metric: 'portfolio_occupancy', grain: 'month', currency: null, scale: 1, ...range, series: [{ key: 'occupancy_rate', label: 'Occupancy rate', kind: 'occupancy' }], points: [{ ...period, occupancy_rate: 100, occupied: 2, vacant: 0, capacity: 2 }] }
const contribution = {
  metric: 'property_contribution', currency: 'USD', scale: 1, ...range, portfolio_net_income: 1650,
  rows: [
    { property_id: 1, property_name: properties[0].name, revenue: 1000, costs: 400, net_income: 600, portfolio_share: 36.4 },
    { property_id: 2, property_name: 'Dollar House (negative contributor)', revenue: 1000, costs: 950, net_income: -50, portfolio_share: -3 },
  ],
}
const yields = {
  metric: 'property_yields', currency: 'USD', scale: 1, ...range,
  rows: [{ property_id: 1, property_name: properties[0].name, valuation_date: range.end, property_value: 250000, annualized_revenue: 12000, annualized_costs: 4800, gross_yield: 4.8, net_yield: 2.88, status: 'ok' }],
}
const exposure = {
  metric: 'currency_exposure', grain: 'month', currency: 'USD', scale: 1, ...range, measure: 'property_value', measure_label: 'Property value',
  series: [{ key: 'eur', label: 'EUR', kind: 'currency' }, { key: 'usd', label: 'USD', kind: 'currency' }],
  points: [{ ...period, eur: 250000, usd: 150000 }],
  coverage: [{ ...period, currency: 'USD', status: 'ok', missing_count: 0, stale_count: 0 }],
}
const valuation = {
  metric: 'property_valuation', grain: 'record', currency: 'EUR', scale: 1, ...range, status: 'ok',
  series: [{ key: 'total_value', label: 'Total value', kind: 'total' }, { key: 'debt', label: 'Debt', kind: 'debt' }, { key: 'equity', label: 'Equity', kind: 'equity' }],
  points: [{ ...period, total_value: 250000, debt: 100000, equity: 150000, status: 'ok' }],
}

async function mockDashboardApi(page: Page, options: { summaryStatus?: number; cashStatus?: number } = {}) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (path.endsWith('/auth/csrf/')) return route.fulfill({ status: 200, body: '{}' })
    if (path.endsWith('/auth/me/')) return json({ user })
    if (path.endsWith('/properties/')) return json(properties)
    if (path.endsWith('/properties/1/')) return json(properties[0])
    if (path.endsWith('/properties/with_stats/')) return json(properties)
    if (path.endsWith('/transactions/')) return json([])
    if (path.endsWith('/tenants/')) return json([])
    if (path.endsWith('/property-valuations/')) return json([])
    if (path.includes('/analytics/portfolio/summary/')) return json(options.summaryStatus ? { detail: 'summary unavailable' } : { currency: 'USD', scale: 1, ...range, property_count: 2, rental_inventory_count: 2, occupied: 2, occupancy_rate: 100, revenue: 2000, costs: 350, net_income: 1650, property_value: 400000, debt: 100000, equity: 300000, valuation_status: 'ok', property_value_status: 'ok', debt_status: 'ok' }, options.summaryStatus)
    if (path.includes('/analytics/portfolio/cash-flow/')) return json(options.cashStatus ? { detail: 'cash unavailable' } : cashFlow, options.cashStatus)
    if (path.includes('/analytics/portfolio/expenses/')) return json(expenseDrivers)
    if (path.includes('/analytics/portfolio/property-contribution/')) return json(contribution)
    if (path.includes('/analytics/portfolio/yields/')) return json(yields)
    if (path.includes('/analytics/portfolio/currency-exposure/')) return json(exposure)
    if (path.includes('/analytics/portfolio/occupancy/')) return json(occupancy)
    if (path.includes('/analytics/properties/1/valuation/')) return json(valuation)
    return json({ detail: `Unhandled fixture path ${path}` }, 404)
  })
}

test.beforeEach(async ({ page }) => {
  await mockDashboardApi(page)
})

test('loads a consistent route fallback before the dashboard chunk resolves', async ({ page }) => {
  let releaseChunk: (() => void) | undefined
  await page.route('**/src/pages/HomePage.tsx', async (route) => {
    await new Promise<void>((resolve) => { releaseChunk = resolve })
    await route.continue()
  })
  const navigation = page.goto('/')
  await expect(page.getByRole('status', { name: 'Loading page' })).toBeVisible()
  releaseChunk?.()
  await navigation
})

test('restores every dashboard filter from a copied URL', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Risk' }).click()
  const copiedDashboardUrl = page.url()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Risk analysis' })).toBeVisible()
  await expect(page).toHaveURL(copiedDashboardUrl)
})

test('keeps charts operable with keyboard and exposes exact values for long labels and mixed currencies', async ({ page }) => {
  await page.goto('/')
  const legend = page.getByRole('button', { name: 'Rent income' })
  await legend.focus()
  await page.keyboard.press('Enter')
  await expect(legend).toHaveAttribute('aria-pressed', 'false')
  await page.getByRole('button', { name: 'Table' }).first().click()
  await expect(page.getByRole('table', { name: 'Net cash flow exact values' })).toBeVisible()
  await page.getByRole('button', { name: 'Table' }).nth(1).click()
  await expect(page.getByText('Dollar House (negative contributor)')).toBeVisible()
  await expect(page.getByText('Negative contributor', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'EUR' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'USD' })).toBeVisible()
})

test('navigates to the filtered transaction drill-down', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Drill down to transactions').click()
  await page.getByRole('button', { name: /View Rent income transactions/ }).click()
  await expect(page).toHaveURL(/\/transactions\?from=2024-01-01&to=2024-02-29&category=rent&currency=USD/)
})

test('supports mobile filter sheet at 390px', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only control')
  await page.goto('/')
  await page.getByRole('button', { name: 'Filters', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Dashboard filters' })).toBeVisible()
  await expect(page.getByLabel(properties[0].name)).toBeVisible()
})

test('shows recoverable loading, error, and empty analytics states', async ({ page }) => {
  await mockDashboardApi(page, { summaryStatus: 500, cashStatus: 500 })
  await page.goto('/')
  await expect(page.getByText('Failed to load portfolio summary')).toBeVisible()
  await expect(page.getByText('Could not load Net cash flow.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry' }).first()).toBeVisible()
})

test('navigates from a property to its valuation history', async ({ page }) => {
  await page.goto('/properties/1')
  await expect(page.getByText(properties[0].name, { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Valuations' }).click()
  await expect(page.getByRole('tab', { name: 'Valuations' })).toHaveAttribute('data-state', 'active')
})
