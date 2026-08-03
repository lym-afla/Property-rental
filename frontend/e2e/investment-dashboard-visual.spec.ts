import { expect, test, type Page } from '@playwright/test'

test.skip(process.platform !== 'win32' || process.env.PW_CHANNEL !== 'chrome', 'Visual baselines are pinned to Windows Chrome.')

const fontRenderingTolerance = { animations: 'disabled' as const, maxDiffPixels: 1000 }
const chartReadinessTimeout = 15_000

async function hideFixedAppChrome(page: Page) {
  await page.locator('body *').evaluateAll((elements) => elements.forEach((element) => {
    if (getComputedStyle(element).position === 'fixed') (element as HTMLElement).style.display = 'none'
  }))
}

test('populated dashboard visual baseline preserves chart layout and exact values at each required viewport', async ({ page }) => {
  test.setTimeout(60_000)
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    if (path.endsWith('/auth/csrf/')) return json({})
    if (path.endsWith('/auth/me/')) return json({ user: { id: 1, username: 'visual', email: 'visual@example.test', first_name: 'Visual', last_name: 'QA', is_landlord: true, is_tenant: false, effective_date: '2024-02-29', default_currency: 'USD', use_default_currency_for_all_data: false, chart_frequency: 'M', chart_timeline: '6m', digits: 0 } })
    if (path.endsWith('/properties/')) return json([{ id: 1, owned_by: 1, name: 'Long Riverside apartment label for visual overflow coverage', location: 'Berlin', address: '1 Test Street', num_bedrooms: 2, area: '70', currency: 'EUR', sold: null }, { id: 2, owned_by: 1, name: 'Dollar House', location: 'New York', address: '2 Test Street', num_bedrooms: 1, area: '45', currency: 'USD', sold: null }])
    if (path.endsWith('/properties/1/')) return json({ id: 1, owned_by: 1, name: 'Long Riverside apartment label for visual overflow coverage', location: 'Berlin', address: '1 Test Street', num_bedrooms: 2, area: '70', currency: 'EUR', sold: null })
    if (path.endsWith('/properties/with_stats/')) return json([])
    if (path.endsWith('/tenants/1/')) return json({ id: 1, user: null, property: 1, first_name: 'Bob', last_name: 'Jones', phone: '+49 30 1234567', email: 'bob@example.test', lease_start: '2024-01-01', lease_end: null, payday: 1 })
    if (path.endsWith('/tenants/with_stats/')) return json([{ id: 1, user: null, property: 1, first_name: 'Bob', last_name: 'Jones', phone: '+49 30 1234567', email: 'bob@example.test', lease_start: '2024-01-01', lease_end: null, payday: 1, rent_rate: '1000.00', revenue_all_time: 24000, revenue_ytd: 2000, debt: -100, stats_currency: 'EUR' }])
    if (path.endsWith('/tenants/')) return json([{ id: 1, user: null, property: 1, first_name: 'Bob', last_name: 'Jones', phone: '+49 30 1234567', email: 'bob@example.test', lease_start: '2024-01-01', lease_end: null, payday: 1 }])
    if (path.endsWith('/transactions/')) return json([{ id: 1, property: 1, tenant: 1, date: '2024-02-15', category: 'cost_reimbursement', period: '2024-02', currency: 'USD', amount: '-250.00', type: 'expense', comment: 'Shared utility charge' }])
    if (path.endsWith('/property-valuations/')) return json([{ id: 1, property: 1, capital_structure_date: '2004-01-01', capital_structure_value: '150000.00', capital_structure_debt: '90000.00' }, { id: 2, property: 1, capital_structure_date: '2023-01-01', capital_structure_value: '240000.00', capital_structure_debt: '105000.00' }, { id: 3, property: 1, capital_structure_date: '2024-01-01', capital_structure_value: '250000.00', capital_structure_debt: '100000.00' }])
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
    if (path.includes('/analytics/portfolio/profit-loss/')) {
      const columns = Array.from({ length: 21 }, (_, index) => { const year = String(2004 + index); return { key: year, label: year === '2024' ? '2024YTD' : year, start: `${year}-01-01`, end: year === '2024' ? range.end : `${year}-12-31` } })
      const positives = Object.fromEntries(columns.map(({ key }, index) => [key, key === '2024' ? 1650 : 1000 + index * 50]))
      const negatives = Object.fromEntries(columns.map(({ key }) => [key, -350]))
      return json({ metric: 'profit_and_loss', currency: 'USD', scale: 1, end: range.end, columns, rows: [{ key: 'rent', label: 'Rent income', kind: 'income', values: positives }, { key: 'repairs', label: 'Repairs', kind: 'expense', values: negatives }, { key: 'total_revenue', label: 'Total revenue', kind: 'total_revenue', values: positives }, { key: 'total_expenses', label: 'Total expenses', kind: 'total_expenses', values: negatives }, { key: 'net_income', label: 'Net income', kind: 'net_income', values: positives }] })
    }
    if (path.includes('/analytics/properties/1/valuation/')) return json({ metric: 'property_valuation', grain: 'record', currency: 'EUR', scale: 1, start: '2004-01-01', end: range.end, status: 'ok', series: [{ key: 'total_value', label: 'Total value', kind: 'total' }, { key: 'debt', label: 'Debt', kind: 'debt' }, { key: 'equity', label: 'Equity', kind: 'equity' }], points: [{ period_start: '2004-01-01', period_end: '2004-01-01', total_value: 150000, debt: 90000, equity: 60000, status: 'ok' }, { period_start: '2023-01-01', period_end: '2023-01-01', total_value: 240000, debt: 105000, equity: 135000, status: 'ok' }, { period_start: '2024-01-01', period_end: '2024-01-01', total_value: 250000, debt: 100000, equity: 150000, status: 'ok' }] })
    if (path.includes('/analytics/tenants/1/rent-performance/')) return json({ metric: 'tenant_rent_performance', grain: 'month', currency: 'EUR', scale: 1, ...range, opening_arrears: 0, opening_issues: [], status: 'ok', issues: [], series: [{ key: 'expected', label: 'Expected rent', kind: 'expected' }, { key: 'received', label: 'Received rent', kind: 'received' }, { key: 'variance', label: 'Variance', kind: 'variance' }, { key: 'cumulative_arrears', label: 'Cumulative arrears', kind: 'cumulative' }], points: [{ ...january, expected: 1000, received: 900, variance: -100, cumulative_arrears: -100, status: 'ok', issues: [] }, { ...february, expected: 1000, received: 950, variance: -50, cumulative_arrears: -150, status: 'ok', issues: [] }] })
    return json([])
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Investment dashboard' })).toBeVisible()
  await expect(page.getByText('Net cash flow', { exact: true })).toBeVisible()
  await expect(page.getByText('Cumulative cash', { exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await hideFixedAppChrome(page)
  const cashFlowCard = page.getByText('Net cash flow', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  const zeroLine = cashFlowCard.locator('.recharts-reference-line-line')
  const incomeBar = cashFlowCard.locator('.recharts-bar-rectangle path[fill="#2563EB"]').first()
  const expenseBar = cashFlowCard.locator('.recharts-bar-rectangle path[fill="#D97706"]').first()
  await expect.poll(async () => {
    const [zeroBox, incomeBox, expenseBox] = await Promise.all([zeroLine.boundingBox(), incomeBar.boundingBox(), expenseBar.boundingBox()])
    if (!zeroBox || !incomeBox || !expenseBox) return false
    return zeroBox.width > 0
      && incomeBox.width > 0
      && incomeBox.height > 0
      && expenseBox.width > 0
      && expenseBox.height > 0
  }, { timeout: chartReadinessTimeout }).toBe(true)

  await expect(cashFlowCard).toHaveScreenshot('investment-dashboard-populated.png', { animations: 'disabled' })

  await page.getByRole('button', { name: 'Table' }).first().click()
  const cashFlowTable = page.getByRole('table', { name: 'Net cash flow exact values' })
  await expect(cashFlowTable).toBeVisible()
  await expect(cashFlowTable).toContainText('($350)')
  await expect(cashFlowTable).toContainText('$2,000')
  await expect(cashFlowCard).toHaveScreenshot('investment-dashboard-populated-table.png', { animations: 'disabled' })

  await page.getByRole('button', { name: 'Portfolio', exact: true }).click()
  const yieldCard = page.getByText('Yield comparison', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  const breakdownCard = page.getByText('Portfolio breakdown by property', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  await expect(yieldCard).toBeVisible()
  await expect(breakdownCard).toBeVisible()
  await expect.poll(async () => yieldCard.locator('.recharts-scatter .recharts-symbols').evaluateAll((symbols) => symbols.length > 0 && symbols.every((symbol) => {
    const box = (symbol as SVGGraphicsElement).getBBox()
    return box.width > 0 && box.height > 0
  })), { timeout: chartReadinessTimeout }).toBe(true)
  await expect.poll(async () => breakdownCard.locator('.recharts-line-curve').evaluateAll((lines) => lines.length > 0 && lines.every((line) => (line as SVGGeometryElement).getTotalLength() > 0)), { timeout: chartReadinessTimeout }).toBe(true)
  await expect(yieldCard).toHaveScreenshot('investment-dashboard-portfolio-yields.png', { animations: 'disabled' })
  await expect(breakdownCard).toHaveScreenshot('investment-dashboard-portfolio-breakdown.png', { animations: 'disabled' })

  await page.getByRole('button', { name: 'Income & Costs' }).click()
  const trendCard = page.getByText('Revenue and expenses', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  const profitLossCard = page.getByText('Profit & Loss', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  await expect(profitLossCard.getByRole('table', { name: 'Profit and Loss statement' })).toBeVisible()
  await expect.poll(async () => trendCard.locator('.recharts-line-curve').evaluateAll((lines) => lines.length === 2 && lines.every((line) => (line as SVGGeometryElement).getTotalLength() > 0)), { timeout: chartReadinessTimeout }).toBe(true)
  await expect(profitLossCard).toHaveScreenshot('investment-dashboard-profit-loss.png', { animations: 'disabled' })
  const profitLossScroller = profitLossCard.getByRole('table', { name: 'Profit and Loss statement' }).locator('xpath=..')
  expect(await profitLossScroller.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
  await profitLossScroller.evaluate((element) => { element.scrollLeft = element.scrollWidth })
  await expect.poll(async () => profitLossScroller.evaluate((element) => element.scrollLeft > 0)).toBe(true)
  const categoryHeader = profitLossCard.getByRole('columnheader', { name: 'Category' })
  const latestYearHeader = profitLossCard.getByRole('columnheader', { name: '2024' })
  await expect.poll(async () => {
    const [categoryBox, latestYearBox] = await Promise.all([categoryHeader.boundingBox(), latestYearHeader.boundingBox()])
    return categoryBox !== null && latestYearBox !== null && latestYearBox.x >= categoryBox.x + categoryBox.width
  }).toBe(true)
  await expect(profitLossCard).toHaveScreenshot('investment-dashboard-profit-loss-latest.png', { animations: 'disabled' })

  await page.goto('/properties/1')
  const valuationCard = page.getByText('Property valuation', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  await expect(valuationCard).toBeVisible()
  await hideFixedAppChrome(page)
  await expect.poll(async () => valuationCard.locator('.recharts-bar-rectangle').evaluateAll((bars) => bars.length === 6 && bars.every((bar) => {
    const box = (bar as SVGGraphicsElement).getBBox()
    return box.width > 0 && box.height > 0
  })), { timeout: chartReadinessTimeout }).toBe(true)
  await expect(valuationCard).toHaveScreenshot('investment-property-valuation.png', fontRenderingTolerance)

  await page.goto('/tenants/1')
  const rentCard = page.getByText('Tenant rent performance', { exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
  await expect(rentCard).toContainText('Native currency: EUR')
  await hideFixedAppChrome(page)
  await expect.poll(async () => rentCard.locator('.recharts-bar-rectangle').evaluateAll((bars) => bars.length > 0 && bars.every((bar) => {
    const box = (bar as SVGGraphicsElement).getBBox()
    return box.width > 0 && box.height > 0
  })), { timeout: chartReadinessTimeout }).toBe(true)
  await expect(rentCard).toHaveScreenshot('investment-tenant-native-currency.png', fontRenderingTolerance)

  await page.goto('/transactions')
  const transactionsTable = page.getByRole('table')
  await expect(transactionsTable).toContainText('Cost reimbursement')
  await expect(transactionsTable).toContainText('($250)')
  await hideFixedAppChrome(page)
  const categoryCell = transactionsTable.locator('[data-slot="table-cell"]').filter({ hasText: 'Cost reimbursement' })
  const amountCell = transactionsTable.locator('[data-slot="table-cell"]').filter({ hasText: '($250)' })
  await categoryCell.scrollIntoViewIfNeeded()
  await expect(categoryCell).toHaveScreenshot('investment-transaction-category.png', { animations: 'disabled' })
  await amountCell.scrollIntoViewIfNeeded()
  await expect(amountCell).toHaveScreenshot('investment-transaction-accounting.png', { animations: 'disabled' })

  await expect(page.locator('body')).not.toContainText('NaN')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
