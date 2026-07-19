import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { fixtureUser } from '@/__fixtures__/user'

// Default MSW handlers — auth endpoints only for now (Task 10).
// Extended per test via `server.use(...)` in Tasks 11 and 12.
const defaultHandlers = [
  http.get('/api/v1/auth/me/', () => HttpResponse.json({ user: fixtureUser })),
  http.post('/api/v1/auth/login/', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    if (body.username === 'alice' && body.password === 'TestPass123!') {
      return HttpResponse.json({ user: fixtureUser })
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 400 })
  }),
  http.post('/api/v1/auth/logout/', () => new HttpResponse(null, { status: 204 })),
  http.post('/api/v1/auth/register/', async ({ request }) => {
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
]

// Single `server` declaration (Task 10 brief flagged a duplicate-declaration
// bug — corrected here by defining `defaultHandlers` first, then exporting
// the server once with them spread in).
export const server = setupServer(...defaultHandlers)
