import { setupServer } from 'msw/node'
import { http, HttpResponse, delay } from 'msw'
import { fixtureUser } from '@/__fixtures__/user'
import {
  fixtureFXList,
  fixtureProperties,
  fixturePropertiesWithStats,
  fixturePropertyValuations,
  fixtureTenants,
  fixtureTenantsWithStats,
  fixtureTransactions,
} from '@/__fixtures__/lists'
import { fixtureProperty } from '@/__fixtures__/property'
import { fixtureTenant } from '@/__fixtures__/tenant'
import { fixtureTransactionIncome } from '@/__fixtures__/transaction'
import { fixtureFX } from '@/__fixtures__/fx'
import { fixturePropertyValuation } from '@/__fixtures__/propertyValuation'

// Default MSW handlers for every endpoint the SPA can hit (Task 10).
//
// Auth handlers preserve the bespoke behavior from earlier tasks (login
// validation, duplicate-username guard) — tests in `auth.test.tsx`,
// `LoginPage.test.tsx`, and `RegisterPage.test.tsx` rely on them. The entity
// handlers below default to returning the Task 9 fixtures verbatim so pages
// in Tasks 11 and 12 render without each suite needing to register handlers
// for every incidental fetch.
//
// `server.use(...)` in individual tests still overrides any of these.

const API = '/api/v1'

const defaultHandlers = [
  // ---- Auth (existing behavior preserved) -------------------------------
  // Task 13: SPA calls this on boot via SessionProvider to prime the
  // csrftoken cookie. Default to a 200 so the request doesn't show up as
  // an unhandled MSW warning in every test.
  http.get(`${API}/auth/csrf/`, () =>
    HttpResponse.json({ detail: 'CSRF cookie set' }),
  ),
  http.get(`${API}/auth/me/`, () => HttpResponse.json({ user: fixtureUser })),
  http.patch(`${API}/auth/me/`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof fixtureUser>
    const merged = { ...fixtureUser, ...body }
    return HttpResponse.json({ user: merged })
  }),
  http.post(`${API}/auth/change-password/`, async ({ request }) => {
    const body = (await request.json()) as {
      old_password: string
      new_password1: string
      new_password2: string
    }
    if (body.old_password !== 'TestPass123!') {
      return HttpResponse.json(
        { old_password: ['Your old password was entered incorrectly.'] },
        { status: 400 },
      )
    }
    if (body.new_password1 !== body.new_password2) {
      return HttpResponse.json(
        { new_password2: ["The two password fields didn't match."] },
        { status: 400 },
      )
    }
    return HttpResponse.json({ detail: 'Password changed' })
  }),
  http.post(`${API}/auth/login/`, async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    if (body.username === 'alice' && body.password === 'TestPass123!') {
      return HttpResponse.json({ user: fixtureUser })
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 400 })
  }),
  http.post(`${API}/auth/logout/`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${API}/auth/register/`, async ({ request }) => {
    const body = (await request.json()) as { username: string }
    if (body.username === 'taken') {
      return HttpResponse.json(
        { username: 'A user with this username already exists.' },
        { status: 400 },
      )
    }
    return HttpResponse.json(
      { user: { ...fixtureUser, username: body.username } },
      { status: 201 },
    )
  }),

  // ---- Properties -------------------------------------------------------
  http.get(`${API}/properties/`, () => HttpResponse.json(fixtureProperties)),
  http.get(`${API}/properties/with_stats/`, () =>
    HttpResponse.json(fixturePropertiesWithStats),
  ),
  http.get(`${API}/properties/:id/`, ({ params }) => {
    const id = Number(params.id)
    const found = fixtureProperties.find((p) => p.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    return HttpResponse.json(found)
  }),
  http.post(`${API}/properties/`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof fixtureProperty>
    return HttpResponse.json({ ...fixtureProperty, ...body, id: 999 }, { status: 201 })
  }),
  http.patch(`${API}/properties/:id/`, async ({ request, params }) => {
    const id = Number(params.id)
    const found = fixtureProperties.find((p) => p.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    const body = (await request.json()) as Partial<typeof fixtureProperty>
    return HttpResponse.json({ ...found, ...body })
  }),
  http.delete(`${API}/properties/:id/`, () => new HttpResponse(null, { status: 204 })),

  // ---- Tenants ----------------------------------------------------------
  http.get(`${API}/tenants/`, () => HttpResponse.json(fixtureTenants)),
  http.get(`${API}/tenants/with_stats/`, () =>
    HttpResponse.json(fixtureTenantsWithStats),
  ),
  http.get(`${API}/tenants/:id/`, ({ params }) => {
    const id = Number(params.id)
    const found = fixtureTenants.find((t) => t.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    return HttpResponse.json(found)
  }),
  http.post(`${API}/tenants/`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof fixtureTenant>
    return HttpResponse.json({ ...fixtureTenant, ...body, id: 999 }, { status: 201 })
  }),
  http.patch(`${API}/tenants/:id/`, async ({ request, params }) => {
    const id = Number(params.id)
    const found = fixtureTenants.find((t) => t.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    const body = (await request.json()) as Partial<typeof fixtureTenant>
    return HttpResponse.json({ ...found, ...body })
  }),
  http.delete(`${API}/tenants/:id/`, () => new HttpResponse(null, { status: 204 })),
  // POST /tenants/<id>/vacate/ body `{ lease_end }` -> 200 `{detail, lease_end}`
  http.post(`${API}/tenants/:id/vacate/`, async ({ request, params }) => {
    const id = Number(params.id)
    const found = fixtureTenants.find((t) => t.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    const body = (await request.json()) as { lease_end: string }
    return HttpResponse.json({
      detail: 'Tenant vacated',
      lease_end: body.lease_end,
    })
  }),

  // ---- Transactions -----------------------------------------------------
  // Returns the full fixture list; per-test handlers can override to filter.
  http.get(`${API}/transactions/`, () => HttpResponse.json(fixtureTransactions)),
  http.get(`${API}/transactions/:id/`, ({ params }) => {
    const id = Number(params.id)
    if (fixtureTransactionIncome.id === id) {
      return HttpResponse.json(fixtureTransactionIncome)
    }
    return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
  }),
  http.post(`${API}/transactions/`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof fixtureTransactionIncome>
    return HttpResponse.json(
      { ...fixtureTransactionIncome, ...body, id: 999 },
      { status: 201 },
    )
  }),
  http.patch(`${API}/transactions/:id/`, async ({ request, params }) => {
    const id = Number(params.id)
    if (fixtureTransactionIncome.id !== id) {
      return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    }
    const body = (await request.json()) as Partial<typeof fixtureTransactionIncome>
    return HttpResponse.json({ ...fixtureTransactionIncome, ...body })
  }),
  http.delete(`${API}/transactions/:id/`, () => new HttpResponse(null, { status: 204 })),

  // ---- FX ---------------------------------------------------------------
  http.get(`${API}/fx/`, () => HttpResponse.json(fixtureFXList)),
  http.get(`${API}/fx/:id/`, ({ params }) => {
    const id = Number(params.id)
    const found = fixtureFXList.find((f) => f.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    return HttpResponse.json(found)
  }),
  http.post(`${API}/fx/`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof fixtureFX>
    return HttpResponse.json({ ...fixtureFX, ...body, id: 999 }, { status: 201 })
  }),
  http.patch(`${API}/fx/:id/`, async ({ request, params }) => {
    const id = Number(params.id)
    const found = fixtureFXList.find((f) => f.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    const body = (await request.json()) as Partial<typeof fixtureFX>
    return HttpResponse.json({ ...found, ...body })
  }),
  http.delete(`${API}/fx/:id/`, () => new HttpResponse(null, { status: 204 })),
  // POST /fx/update/ -> 200 `{detail: "FX rates updated"}`.
  // Tiny delay so tests can exercise pending state if they choose to.
  http.post(`${API}/fx/update/`, async () => {
    await delay(10)
    return HttpResponse.json({ detail: 'FX rates updated' })
  }),

  // ---- Property valuations ---------------------------------------------
  // GET supports the `?property=` filter the `byProperty` hook sends.
  http.get(`${API}/property-valuations/`, ({ request }) => {
    const url = new URL(request.url)
    const propertyId = url.searchParams.get('property')
    if (propertyId !== null) {
      const filtered = fixturePropertyValuations.filter(
        (v) => v.property === Number(propertyId),
      )
      return HttpResponse.json(filtered)
    }
    return HttpResponse.json(fixturePropertyValuations)
  }),
  http.get(`${API}/property-valuations/:id/`, ({ params }) => {
    const id = Number(params.id)
    const found = fixturePropertyValuations.find((v) => v.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    return HttpResponse.json(found)
  }),
  http.post(`${API}/property-valuations/`, async ({ request }) => {
    const body = (await request.json()) as Partial<typeof fixturePropertyValuation>
    return HttpResponse.json(
      { ...fixturePropertyValuation, ...body, id: 999 },
      { status: 201 },
    )
  }),
  http.patch(`${API}/property-valuations/:id/`, async ({ request, params }) => {
    const id = Number(params.id)
    const found = fixturePropertyValuations.find((v) => v.id === id)
    if (!found) return HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
    const body = (await request.json()) as Partial<typeof fixturePropertyValuation>
    return HttpResponse.json({ ...found, ...body })
  }),
  http.delete(`${API}/property-valuations/:id/`, () => new HttpResponse(null, { status: 204 })),

  // ---- Chart data -------------------------------------------------------
  // ChartDataView requires `type`, `id`, `freq`, `start`, `end`. Default to
  // an empty series so any chart-mounted test doesn't blow up; tests that
  // care about the shape should override via `server.use(...)`.
  http.get(`${API}/chart-data/`, () =>
    HttpResponse.json({
      labels: [],
      income: [],
      expense: [],
      net: [],
    }),
  ),
]

// Single `server` declaration (Task 10 brief flagged a duplicate-declaration
// bug — corrected here by defining `defaultHandlers` first, then exporting
// the server once with them spread in).
export const server = setupServer(...defaultHandlers)
