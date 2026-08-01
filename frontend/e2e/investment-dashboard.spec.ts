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
  series: [
    { key: 'rent', label: 'Rent income', kind: 'income_category' },
    { key: 'repairs', label: 'Repairs', kind: 'expense_category' },
    { key: 'total_income', label: 'Total income', kind: 'income_total' },
    { key: 'total_expenses', label: 'Total expenses', kind: 'expense_total' },
    { key: 'net_income', label: 'Net income', kind: 'net' },
    { key: 'cumulative_net_income', label: 'Cumulative net income', kind: 'cumulative' },
  ],
  points: [
    { period_start: '2024-01-01', period_end: '2024-01-31', rent: 900, repairs: -150, total_income: 900, total_expenses: -150, net_income: 750, cumulative_net_income: 750 },
    { period_start: '2024-02-01', period_end: '2024-02-29', rent: 1100, repairs: -200, total_income: 1100, total_expenses: -200, net_income: 900, cumulative_net_income: 1650 },
  ],
}
const expenseDrivers = { ...cashFlow, metric: 'expense_drivers', series: [{ key: 'repairs', label: 'Repairs', kind: 'expense_category' }], points: [{ period_start: '2024-01-01', period_end: '2024-01-31', repairs: -150 }, { period_start: '2024-02-01', period_end: '2024-02-29', repairs: -200 }] }
const occupancy = {
  metric: 'portfolio_occupancy', grain: 'month', currency: null, scale: 1, ...range,
  series: [
    { key: 'capacity', label: 'Rental inventory', kind: 'capacity' },
    { key: 'occupied', label: 'Occupied', kind: 'occupied' },
    { key: 'vacant', label: 'Vacant', kind: 'vacant' },
    { key: 'occupancy_rate', label: 'Occupancy rate', kind: 'occupancy_rate' },
  ],
  points: [{ ...period, occupancy_rate: 100, occupied: 2, vacant: 0, capacity: 2 }],
}
const contribution = {
  metric: 'property_contribution', currency: 'USD', scale: 1, ...range, portfolio_net_income: 1650,
  rows: [
    { property_id: 1, property_name: properties[0].name, revenue: 1000, costs: 400, net_income: 600, portfolio_share: 36.4 },
    { property_id: 2, property_name: 'Dollar House (negative contributor)', revenue: 1000, costs: 950, net_income: -50, portfolio_share: -3 },
  ],
}
const yields = {
  metric: 'property_yields', currency: 'USD', scale: 1, ...range,
  rows: [{ property_id: 1, property_name: properties[0].name, valuation_date: range.end, property_value: 250000, debt: 100000, equity: 150000, annualized_revenue: 12000, annualized_costs: 4800, gross_yield: 4.8, equity_yield: 4.8, status: 'ok' }],
}
const propertyBreakdown = {
  metric: 'property_breakdown', grain: 'month', currency: 'USD', scale: 1, ...range, measure: 'property_value', measure_label: 'Property value',
  series: [{ key: 'property_1', label: properties[0].name, kind: 'property' }, { key: 'property_2', label: properties[1].name, kind: 'property' }],
  points: [{ ...period, property_1: 250000, property_2: 150000 }],
  coverage: [{ ...period, property_id: 1, status: 'ok' }, { ...period, property_id: 2, status: 'ok' }],
}
const valuation = {
  metric: 'property_valuation', grain: 'record', currency: 'EUR', scale: 1, start: '2004-01-01', end: range.end, status: 'ok',
  series: [{ key: 'total_value', label: 'Total value', kind: 'total' }, { key: 'debt', label: 'Debt', kind: 'debt' }, { key: 'equity', label: 'Equity', kind: 'equity' }],
  points: [
    { period_start: '2004-01-01', period_end: '2004-01-01', total_value: 150000, debt: 90000, equity: 60000, status: 'ok' },
    { period_start: '2023-01-01', period_end: '2023-01-01', total_value: 240000, debt: 105000, equity: 135000, status: 'ok' },
    { period_start: '2024-01-01', period_end: '2024-01-01', total_value: 250000, debt: 100000, equity: 150000, status: 'ok' },
  ],
}
const tenant = {
  id: 1, user: null, property: 1, first_name: 'Bob', last_name: 'Jones',
  phone: '+49 30 1234567', email: 'bob@example.test', lease_start: range.start,
  lease_end: null, payday: 1,
}
const tenantWithStats = {
  ...tenant, rent_rate: '1000.00', revenue_all_time: 24000, revenue_ytd: 2000,
  debt: -100, stats_currency: 'EUR',
}
const transactions = [{
  id: 1, property: 1, tenant: 1, date: '2024-02-15',
  category: 'cost_reimbursement', period: '2024-02', currency: 'USD',
  amount: '-250.00', type: 'expense', comment: 'Shared utility charge',
}]
const profitLossColumns = [
  ...Array.from({ length: 21 }, (_, index) => {
    const year = String(2004 + index)
    return { key: year, label: year === '2024' ? '2024YTD' : year, start: `${year}-01-01`, end: year === '2024' ? range.end : `${year}-12-31` }
  }),
]
const profitLossValues = Object.fromEntries(profitLossColumns.map(({ key }, index) => [key, key === '2024' ? 1650 : 1000 + index * 50]))
const profitLoss = {
  metric: 'profit_and_loss', currency: 'USD', scale: 1, end: range.end,
  columns: profitLossColumns,
  rows: [
    { key: 'rent', label: 'Rent income', kind: 'income', values: profitLossValues },
    { key: 'repairs', label: 'Repairs', kind: 'expense', values: Object.fromEntries(profitLossColumns.map(({ key }) => [key, -350])) },
    { key: 'total_revenue', label: 'Total revenue', kind: 'total_revenue', values: profitLossValues },
    { key: 'total_expenses', label: 'Total expenses', kind: 'total_expenses', values: Object.fromEntries(profitLossColumns.map(({ key }) => [key, -350])) },
    { key: 'net_income', label: 'Net income', kind: 'net_income', values: Object.fromEntries(profitLossColumns.map(({ key }, index) => [key, key === '2024' ? 1300 : 650 + index * 50])) },
  ],
}
const rentPerformance = {
  metric: 'tenant_rent_performance', grain: 'month', currency: 'EUR', scale: 1,
  ...range, opening_arrears: 0, opening_issues: [], status: 'ok', issues: [],
  series: [
    { key: 'expected', label: 'Expected rent', kind: 'expected' },
    { key: 'received', label: 'Received rent', kind: 'received' },
    { key: 'variance', label: 'Variance', kind: 'variance' },
    { key: 'cumulative_arrears', label: 'Cumulative arrears', kind: 'cumulative' },
  ],
  points: [{ ...period, expected: 1000, received: 900, variance: -100, cumulative_arrears: -100, status: 'ok', issues: [] }],
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
    if (path.endsWith('/transactions/')) return json(transactions)
    if (path.endsWith('/tenants/1/')) return json(tenant)
    if (path.endsWith('/tenants/with_stats/')) return json([tenantWithStats])
    if (path.endsWith('/tenants/')) return json([tenant])
    if (path.endsWith('/property-valuations/')) return json([
      { id: 1, property: 1, capital_structure_date: '2004-01-01', capital_structure_value: '150000.00', capital_structure_debt: '90000.00' },
      { id: 2, property: 1, capital_structure_date: '2023-01-01', capital_structure_value: '240000.00', capital_structure_debt: '105000.00' },
      { id: 3, property: 1, capital_structure_date: '2024-01-01', capital_structure_value: '250000.00', capital_structure_debt: '100000.00' },
    ])
    if (path.includes('/analytics/portfolio/summary/')) return json(options.summaryStatus ? { detail: 'summary unavailable' } : { currency: 'USD', scale: 1, ...range, property_count: 2, rental_inventory_count: 2, occupied: 2, occupancy_rate: 100, revenue: 2000, costs: 350, net_income: 1650, property_value: 400000, debt: 100000, equity: 300000, valuation_status: 'ok', property_value_status: 'ok', debt_status: 'ok' }, options.summaryStatus)
    if (path.includes('/analytics/portfolio/cash-flow/')) return json(options.cashStatus ? { detail: 'cash unavailable' } : cashFlow, options.cashStatus)
    if (path.includes('/analytics/portfolio/expenses/')) return json(expenseDrivers)
    if (path.includes('/analytics/portfolio/property-contribution/')) return json(contribution)
    if (path.includes('/analytics/portfolio/yields/')) return json(yields)
    if (path.includes('/analytics/portfolio/property-breakdown/')) return json(propertyBreakdown)
    if (path.includes('/analytics/portfolio/occupancy/')) return json(occupancy)
    if (path.includes('/analytics/portfolio/profit-loss/')) {
      const currency = new URL(route.request().url()).searchParams.get('currency') ?? 'USD'
      return json({ ...profitLoss, currency })
    }
    if (path.includes('/analytics/properties/1/valuation/')) return json(valuation)
    if (path.includes('/analytics/tenants/1/rent-performance/')) return json(rentPerformance)
    return json({ detail: `Unhandled fixture path ${path}` }, 404)
  })
}

async function expectReleaseSafeDocument(page: Page) {
  await expect(page.locator('body')).not.toContainText('NaN')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

test.beforeEach(async ({ page }) => {
  await mockDashboardApi(page)
})

test('mobile app navigation keeps every destination touch-sized without horizontal overflow', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile')
  await page.goto('/')
  const navigation = page.getByRole('navigation', { name: 'Primary' })
  await expect(navigation).toBeVisible()
  const links = navigation.getByRole('link')
  await expect(links).toHaveCount(5)
  for (const link of await links.all()) {
    const box = await link.boundingBox()
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
    expect(box?.width ?? 0).toBeGreaterThanOrEqual(44)
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
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

test('restores every supported dashboard filter from a copied URL', async ({ page }, testInfo) => {
  await page.goto('/?section=risk&start=2024-01-01&end=2024-02-29&currency=EUR&grain=quarter&comparison=previous_period&property=1&property=2')
  await expect(page.getByRole('heading', { name: 'Risk analysis' })).toBeVisible()
  await page.getByRole('button', { name: 'Show settings' }).click()
  await expect(page.getByLabel('Start date')).toHaveValue('2024-01-01')
  await expect(page.getByLabel('As of date')).toHaveValue('2024-02-29')
  await expect(page.getByLabel('Reporting currency')).toHaveText('EUR')
  if (testInfo.project.name === 'mobile') {
    await page.getByRole('button', { name: 'Filters', exact: true }).click()
    await expect(page.getByLabel(properties[0].name)).toBeChecked()
    await expect(page.getByLabel(properties[1].name)).toBeChecked()
  } else {
    await expect(page.getByLabel('Properties')).toHaveText('2 selected')
  }
  await expect(page.getByLabel('Frequency')).toHaveText('Quarterly')
  await expect(page.getByLabel('Comparison')).toHaveCount(0)
})

test('keeps charts operable with keyboard and exposes exact values plus property breakdown controls', async ({ page }) => {
  await page.goto('/')
  const legend = page.getByRole('button', { name: 'Rent income' })
  await legend.focus()
  await page.keyboard.press('Enter')
  await expect(legend).toHaveAttribute('aria-pressed', 'false')
  await page.getByRole('button', { name: 'Table' }).first().click()
  const cashFlowTable = page.getByRole('table', { name: 'Net cash flow exact values' })
  await expect(cashFlowTable).toBeVisible()
  await expect(cashFlowTable).toContainText('($150)')
  await page.getByRole('button', { name: 'Portfolio' }).click()
  await page.getByRole('button', { name: 'Table' }).first().click()
  await expect(page.getByText('Dollar House (negative contributor)')).toBeVisible()
  await expect(page.getByText('Negative contributor', { exact: true })).toBeVisible()
  await expect(page.getByText('Portfolio breakdown by property', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Portfolio breakdown measure')).toHaveValue('property_value')
})

test('navigates to the filtered transaction drill-down', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Drill down to transactions').click()
  await page.getByRole('button', { name: 'View Rent income transactions for Jan 1, 2024' }).click()
  await expect(page).toHaveURL(/\/transactions\?from=2024-01-01&to=2024-01-31&category=rent&currency=USD/)
})

test('supports mobile filter sheet at 390px', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only control')
  await page.goto('/')
  await page.getByRole('button', { name: 'Show settings' }).click()
  await page.getByRole('button', { name: 'Filters', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Dashboard filters' })).toBeVisible()
  await expect(page.getByLabel(properties[0].name)).toBeVisible()
})

test('keeps dashboard settings compact and touch-safe across viewports', async ({ page }, testInfo) => {
  await page.goto('/')

  const settingsToggle = page.getByRole('button', { name: 'Show settings' })
  await expect(settingsToggle).toBeVisible()
  await expect(settingsToggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByLabel('Start date')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await settingsToggle.click()
  await expect(page.getByRole('button', { name: 'Hide settings' })).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByLabel('Start date')).toBeVisible()

  for (const control of [page.getByLabel('Start date'), page.getByLabel('As of date'), page.getByLabel('Reporting currency')]) {
    const box = await control.boundingBox()
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
  }

  if (testInfo.project.name === 'mobile') {
    const filters = page.getByRole('button', { name: 'Filters', exact: true })
    expect((await filters.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44)
    await filters.click()
    const propertiesLabel = page.getByRole('dialog', { name: 'Dashboard filters' }).getByText('Properties', { exact: true })
    const property = page.getByLabel(properties[0].name)
    await expect(propertiesLabel).toBeVisible()
    await expect(property).toBeVisible()
    const labelBox = await propertiesLabel.boundingBox()
    const propertyBox = await property.boundingBox()
    expect(labelBox).not.toBeNull()
    expect(propertyBox).not.toBeNull()
    expect(labelBox!.y + labelBox!.height).toBeLessThanOrEqual(propertyBox!.y)
  } else {
    const filterCard = page.getByLabel('Global dashboard filters')
    const propertiesLabel = filterCard.getByText('Properties', { exact: true })
    const selector = filterCard.getByRole('button', { name: 'Properties' })
    await expect(propertiesLabel).toBeVisible()
    await expect(selector).toBeVisible()
    const labelBox = await propertiesLabel.boundingBox()
    const selectorBox = await selector.boundingBox()
    expect(labelBox).not.toBeNull()
    expect(selectorBox).not.toBeNull()
    expect(labelBox!.y + labelBox!.height).toBeLessThanOrEqual(selectorBox!.y)
    expect(selectorBox!.height).toBeGreaterThanOrEqual(44)
  }

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('shows recoverable loading, error, and empty analytics states', async ({ page }) => {
  await mockDashboardApi(page, { summaryStatus: 500, cashStatus: 500 })
  await page.goto('/')
  await expect(page.getByText('Failed to load portfolio summary')).toBeVisible()
  await expect(page.getByText('Could not load Net cash flow.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry' }).first()).toBeVisible()
})

test('shows semantic chart loading and empty states', async ({ page }) => {
  let releaseCashFlow: (() => void) | undefined
  await page.route('**/api/v1/analytics/portfolio/cash-flow/**', async (route) => {
    await new Promise<void>((resolve) => { releaseCashFlow = resolve })
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(cashFlow) })
  })
  const navigation = page.goto('/')
  await expect(page.getByLabel('Net cash flow loading')).toBeVisible()
  releaseCashFlow?.()
  await navigation

  await page.route('**/api/v1/analytics/portfolio/cash-flow/**', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...cashFlow, points: [] }) }),
  )
  await page.reload()
  await expect(page.getByText('No Net cash flow data for this selection.')).toBeVisible()
})

test('navigates from a property to its valuation history', async ({ page }) => {
  await page.goto('/properties/1')
  await expect(page.getByText(properties[0].name, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Table' }).click()
  await expect(page.getByRole('table', { name: 'Property valuation exact values' })).toContainText('€250,000')
  await page.getByRole('tab', { name: 'Valuations' }).click()
  await expect(page.getByRole('tab', { name: 'Valuations' })).toHaveAttribute('data-state', 'active')
})

test('verifies the financial analytics release contract across dashboard, property, tenant, and transactions', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Show settings' })).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByLabel('Portfolio summary')).toContainText('$100,000')
  await expect(page.getByLabel('Portfolio summary')).toContainText('$300,000')
  await expectReleaseSafeDocument(page)

  await page.getByRole('button', { name: 'Show settings' }).click()
  await expect(page.getByRole('button', { name: 'Hide settings' })).toHaveAttribute('aria-expanded', 'true')
  await expectReleaseSafeDocument(page)

  await page.getByRole('button', { name: 'Portfolio', exact: true }).click()
  await expect(page.getByText('Yield comparison', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Yield definitions' }).click()
  await expect(page.getByText('Gross yield — annualized rental income net of costs divided by the latest property value.')).toBeVisible()
  await expect(page.getByText('Equity yield — annualized rental income net of costs divided by equity.')).toBeVisible()
  await page.keyboard.press('Escape')
  await expectReleaseSafeDocument(page)

  await page.getByRole('button', { name: 'Income & Costs' }).click()
  await expect(page.getByText('Profit & Loss', { exact: true })).toBeVisible()
  await expect(page.getByRole('table', { name: 'Profit and Loss statement' })).toBeVisible()
  const trendCard = page.getByText('Revenue and expenses', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  const trendLines = trendCard.locator('.recharts-line-curve')
  await expect(trendLines).toHaveCount(2)
  await expect.poll(async () => trendLines.evaluateAll((lines) => lines.every((line) => {
    const dasharray = getComputedStyle(line).strokeDasharray
    if (dasharray === 'none') return true
    const firstDashLength = Number.parseFloat(dasharray)
    return firstDashLength >= (line as SVGGeometryElement).getTotalLength() * 0.99
  }))).toBe(true)
  await expectReleaseSafeDocument(page)

  await page.goto('/properties/1')
  const propertyProfitLoss = page.getByRole('table', { name: 'Profit and Loss statement' })
  await expect(propertyProfitLoss).toBeVisible()
  const profitLossScroller = propertyProfitLoss.locator('xpath=..')
  expect(await profitLossScroller.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
  await expect(propertyProfitLoss).toContainText('2004')
  await expect(propertyProfitLoss).toContainText('2023')

  const valuationBars = page.getByText('Property valuation', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]').locator('.recharts-bar-rectangle')
  await expect(valuationBars).toHaveCount(6)
  const readValuationCenters = () => valuationBars.evaluateAll((bars) => [...new Set(bars.map((bar) => {
    const box = (bar as SVGGraphicsElement).getBBox()
    return Math.round(box.x + box.width / 2)
  }))].sort((left, right) => left - right))
  await expect.poll(async () => {
    const valuationCenters = await readValuationCenters()
    if (valuationCenters.length !== 3) return false
    const recentGap = valuationCenters[2] - valuationCenters[1]
    return recentGap > 0 && (valuationCenters[1] - valuationCenters[0]) / recentGap > 10
  }).toBe(true)
  await expectReleaseSafeDocument(page)

  await page.goto('/tenants/1')
  await expect(page.getByText('Native currency: EUR · Reporting period: 2024-01-01 to 2024-02-29')).toBeVisible()
  await page.getByRole('button', { name: 'Table' }).click()
  await expect(page.getByRole('table', { name: 'Tenant rent performance exact values' })).toContainText('(€100)')
  await expectReleaseSafeDocument(page)

  await page.goto('/transactions')
  await expect(page.getByText('Cost reimbursement', { exact: true })).toBeVisible()
  await expect(page.getByText('cost_reimbursement', { exact: true })).toHaveCount(0)
  await expect(page.getByText('($250)', { exact: true })).toBeVisible()
  await expectReleaseSafeDocument(page)
})
