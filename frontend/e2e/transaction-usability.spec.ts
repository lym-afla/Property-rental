import { expect, test } from '@playwright/test'
import { fixtureUser } from '../src/__fixtures__/user'
import { fixtureProperty, fixturePropertyAlt } from '../src/__fixtures__/property'
import { fixtureTenant } from '../src/__fixtures__/tenant'
import { fixtureTransactionIncome } from '../src/__fixtures__/transaction'

test('sorts transactions and submits native currency with an optional former tenant', async ({ page }) => {
  let saved: Record<string, unknown> | undefined
  let tenantRequests = 0
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ json: body })
    if (path.endsWith('/auth/me/')) return json({ user: fixtureUser })
    if (path.endsWith('/auth/csrf/')) return json({})
    if (path.endsWith('/properties/')) return json([fixtureProperty, { ...fixturePropertyAlt, currency: 'GBP' }])
    if (path.endsWith('/tenants/')) {
      tenantRequests++
      return json([
        { ...fixtureTenant, first_name: 'Former', lease_end: '2000-01-01' },
        { ...fixtureTenant, id: 2, first_name: 'Current', lease_end: null },
      ])
    }
    if (path.endsWith('/transactions/')) {
      if (route.request().method() === 'POST') {
        saved = route.request().postDataJSON()
        return json({ ...saved, id: 3 })
      }
      return json([
        { ...fixtureTransactionIncome, id: 1, amount: '1000', comment: 'Larger payment' },
        { ...fixtureTransactionIncome, id: 2, amount: '90', comment: 'Smaller payment' },
      ])
    }
    return json([])
  })
  await page.goto('/transactions')
  await expect(page).toHaveTitle('Rent')
  const icon = await page.locator('link[rel="icon"]').getAttribute('href')
  const iconResponse = await page.request.get(icon!)
  expect(iconResponse.ok()).toBe(true)
  expect(iconResponse.headers()['content-type']).toContain('image/svg+xml')
  await page.getByRole('button', { name: 'Amount', exact: true }).click()
  await expect(page.getByRole('row').nth(1)).toContainText('Smaller payment')
  await page.getByRole('button', { name: 'New Transaction' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('combobox', { name: 'Property', exact: true }).click()
  await page.getByRole('option', { name: 'Riverside Flat' }).click()
  await expect(dialog.getByRole('combobox', { name: 'Currency' })).toContainText('EUR')
  await dialog.getByLabel('Date', { exact: true }).fill('2024-01-01')
  await dialog.getByRole('combobox', { name: 'Tenant (optional)' }).click()
  await expect(page.getByRole('option', { name: 'Current Jones' })).toBeVisible()
  await expect(page.getByRole('option', { name: /Former/ })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await dialog.getByRole('checkbox', { name: 'Show former tenants' }).check()
  await dialog.getByRole('combobox', { name: 'Tenant (optional)' }).click()
  await page.getByRole('option', { name: 'Former Jones · Former tenant' }).click()
  await dialog.getByLabel('Amount', { exact: true }).fill('125')
  expect(tenantRequests).toBe(1)
  await dialog.getByRole('button', { name: /save/i }).click()
  await expect(dialog).toHaveCount(0)
  expect(saved).toMatchObject({ property: 1, tenant: 1, currency: 'EUR', amount: '125', date: '2024-01-01' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
