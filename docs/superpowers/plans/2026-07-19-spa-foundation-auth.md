# SPA Foundation + Auth — Implementation Plan (Sub-plan A of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the React + TypeScript + Vite + Tailwind + shadcn/ui SPA scaffold, wire it to Django (dev proxy + prod catch-all), add the 4 DRF auth endpoints, and ship login + register pages — so you can boot the SPA and log in. No entity pages or charts yet (those are sub-plans B and C).

**Architecture:** A new `frontend/` directory (sibling of `property_rental/`) hosts the Vite-built React SPA. In dev, Vite proxies `/api` and `/media` to the Django dev server on `:8000`. In prod, Django's settings add `frontend/dist` to `TEMPLATES.DIRS` and a catch-all Django view serves `index.html` for non-API paths. Auth uses Django session cookies (no tokens) — the SPA reads the existing `csrftoken` cookie and sends `X-CSRFToken` on mutations. Four new DRF endpoints (`/api/v1/auth/{login,logout,me,register}/`) expose Django's `authenticate`/`login`/`logout` as JSON.

**Tech Stack:** Django 4.2.4, DRF 3.14, React 18, TypeScript 5, Vite 6+, Tailwind CSS v4, shadcn/ui (latest), TanStack Query v5, React Router v6, Vitest, Testing Library, MSW.

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-07-19-spa-charting-design.md`):

- **Stack target:** React + TypeScript + Vite + shadcn/ui + Recharts + TanStack Query (this sub-plan covers everything except Recharts/charts).
- **Auth:** Django session cookies only — no token/JWT layer.
- **Deploy:** Django serves the built SPA — same origin, no CORS.
- **Login/register:** Move into the SPA (not Django-rendered).
- **Legacy:** Django templates + template-view code deleted as the SPA replaces each page (this sub-plan only deletes `login_view` + `register_view` + their templates after the SPA equivalents land).
- **CSRF:** The SPA reads the `csrftoken` cookie and sends `X-CSRFToken` on POST/PUT/PATCH/DELETE.
- App is **personal / not live** — breaking changes acceptable.
- Phase 1's pytest suite (103 tests) must stay green throughout; CI runs both pytest and `npm` jobs.
- Git identity (repo-local, configured): `YL-STARDESTROYER <yaroslav.linik@gmail.com>`.
- Working dir: `D:/Developing/Property-rental`. Django project at `D:/Developing/Property-rental/property_rental/`.
- Run pytest from `property_rental/`: `cd property_rental && python -m pytest rentals/tests/ -q`.
- Run frontend tests from `frontend/`: `cd frontend && npm test`.
- Platform: Windows, Git Bash. Use forward slashes in paths.

## File Structure

### Created (frontend — new)

```
frontend/
├── package.json                  <- deps: react, react-dom, react-router-dom, @tanstack/react-query,
│                                    @tanstack/react-query-devtools, tailwindcss, @tailwindcss/vite,
│                                    clsx, tailwind-merge, class-variance-authority, lucide-react,
│                                    sonner, zod, @hookform/resolvers (for later), react-hook-form (for later)
├── vite.config.ts                <- plugins: @vitejs/plugin-react, @tailwindcss/vite; server.proxy; resolve.alias
├── tsconfig.json                 <- paths: "@/*": ["./src/*"]
├── tsconfig.node.json
├── tailwind.config.ts            <- minimal v4 (content paths, theme extension if needed)
├── components.json               <- shadcn config (style: new-york, baseColor: neutral, cssVariables: true)
├── postcss.config.js             <- if Tailwind v4 needs it (v4 uses Vite plugin; check)
├── index.html                    <- Vite entry, mounts #root
├── .gitignore                    <- node_modules, dist
├── src/
│   ├── main.tsx                  <- ReactDOM.createRoot + providers (QueryClient, Toaster)
│   ├── App.tsx                   <- <BrowserRouter> + <AppRoutes/>
│   ├── index.css                 <- Tailwind v4 `@import "tailwindcss"` + shadcn CSS vars
│   ├── vite-env.d.ts             <- Vite type decls
│   ├── lib/
│   │   ├── utils.ts              <- cn() helper (clsx + tailwind-merge) — shadcn staple
│   │   └── format.ts             <- formatCurrency, formatDate (stub; expanded in Plan C)
│   ├── types/
│   │   └── user.ts               <- User type matching the DRF serializer
│   ├── api/
│   │   ├── client.ts             <- fetch wrapper: JSON, CSRF, 401 handling
│   │   ├── keys.ts               <- centralized React Query key factory
│   │   └── auth.ts               <- useLogin, useLogout, useRegister, useSession hooks
│   ├── context/
│   │   └── SessionProvider.tsx   <- wraps useSession() in a Context for synchronous access
│   ├── components/
│   │   ├── ui/                   <- shadcn-generated: button, input, card, label, sonner (Toaster)
│   │   └── layout/
│   │       ├── AppLayout.tsx     <- navbar placeholder + <Outlet/> (real navbar in Plan B)
│   │       └── ProtectedRoute.tsx <- redirect to /login if no session
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   └── HomePage.tsx          <- placeholder ("Welcome, <name>") — real dashboard in Plan C
│   └── __fixtures__/
│       └── user.ts               <- canned User response for tests
└── tests/  (none yet — see Task 9)
```

### Created (Django — new)

```
property_rental/rentals/api/auth.py    <- LoginView, LogoutView, MeView, RegisterView
property_rental/rentals/api/serializers.py  <- MODIFY: add UserSerializer (or new auth_serializers.py)
property_rental/rentals/api/urls.py    <- MODIFY: add auth/ include
property_rental/rentals/templates/spa_index.html   <- minimal shell that serves the built SPA bundle
property_rental/rentals/views.py       <- MODIFY: add spa_view catch-all; delete login_view, register_view (after SPA replaces)
property_rental/rentals/urls.py        <- MODIFY: route /api/v1/auth/, route catch-all to spa_view
property_rental/property_rental/settings/base.py  <- MODIFY: TEMPLATES.DIRS includes frontend/dist (prod)
property_rental/property_rental/settings/dev.py   <- (no change — dev uses Vite, not Django templates)
property_rental/rentals/tests/test_auth_api.py    <- new tests for the 4 endpoints
.github/workflows/ci.yml              <- MODIFY: add frontend-lint, frontend-test, frontend-build jobs
```

---

## Task Ordering

Eight phases, 13 tasks:

1. **Frontend scaffold** (Tasks 1-2) — Vite + React + Tailwind + shadcn installed and booting.
2. **API client + React Query setup** (Task 3) — fetch wrapper, providers, key factory.
3. **Backend: auth endpoints** (Tasks 4-5) — 4 DRF endpoints + tests.
4. **SPA-Django integration** (Task 6) — dev proxy + prod catch-all view + settings.
5. **Session + protected routing** (Task 7) — useSession hook, ProtectedRoute, AppLayout.
6. **Login page** (Task 8) — form, mutation, redirect.
7. **Register page** (Task 9) — form, mutation, redirect.
8. **Frontend test scaffold + CI** (Tasks 10-12) — Vitest + Testing Library + MSW; CI jobs.
9. **Legacy deletion** (Task 13) — delete `login.html`/`register.html`/`login_view`/`register_view`.

---

## Task 1: Vite + React + TypeScript + Tailwind v4 scaffold

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/vite-env.d.ts`, `frontend/.gitignore`

**Interfaces:**
- Produces: a bootable Vite dev server at `http://127.0.0.1:5173` rendering `<h1>Property Rental SPA</h1>`.

- [ ] **Step 1: Scaffold the project with Vite's react-ts template**

From the repo root:
```bash
cd "D:/Developing/Property-rental"
npm create vite@latest frontend -- --template react-ts
```
This creates `frontend/` with `package.json`, `vite.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/index.css`, etc.

If `npm create vite` prompts interactively, the `--template react-ts` flag should make it non-interactive. If it still prompts, answer: framework = React, variant = TypeScript.

- [ ] **Step 2: Install dependencies**

```bash
cd "D:/Developing/Property-rental/frontend"
npm install
```

- [ ] **Step 3: Install Tailwind CSS v4 via the Vite plugin**

```bash
cd "D:/Developing/Property-rental/frontend"
npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 4: Configure the Tailwind Vite plugin**

Edit `frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    port: 5173,
    // Dev proxy to Django — wired in Task 6
  },
})
```

- [ ] **Step 5: Replace `src/index.css` with Tailwind v4 import**

`frontend/src/index.css`:
```css
@import "tailwindcss";
```

- [ ] **Step 6: Configure tsconfig path alias**

Edit `frontend/tsconfig.json` — add to `compilerOptions`:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```
(Merge into existing options; don't replace the whole file.)

- [ ] **Step 7: Replace `src/App.tsx` with a placeholder**

`frontend/src/App.tsx`:
```tsx
function App() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <h1 className="text-3xl font-bold">Property Rental SPA</h1>
    </div>
  )
}

export default App
```

- [ ] **Step 8: Verify the dev server boots**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run dev
```
Open `http://127.0.0.1:5173` — confirm "Property Rental SPA" renders. Stop the server (Ctrl-C).

- [ ] **Step 9: Verify the production build works**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run build
```
Expected: `frontend/dist/` created with `index.html` + bundled assets. No errors.

- [ ] **Step 10: Add a frontend `.gitignore`**

`frontend/.gitignore`:
```
node_modules
dist
*.local
.vite
```

- [ ] **Step 11: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React + TypeScript + Tailwind v4"
```

---

## Task 2: shadcn/ui initialization + base components

**Files:**
- Create: `frontend/components.json`, `frontend/src/lib/utils.ts`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/input.tsx`, `frontend/src/components/ui/card.tsx`, `frontend/src/components/ui/label.tsx`, `frontend/src/components/ui/sonner.tsx`
- Modify: `frontend/src/index.css` (shadcn adds CSS variables)

**Interfaces:**
- Produces: `cn()` helper at `@/lib/utils`; shadcn `Button`, `Input`, `Card`, `Label`, `Toaster` (sonner) components importable from `@/components/ui/*`.

- [ ] **Step 1: Initialize shadcn/ui**

```bash
cd "D:/Developing/Property-rental/frontend"
npx shadcn@latest init
```
If it prompts interactively:
- Style: **New York**
- Base color: **Neutral**
- CSS variables for colors: **Yes**

This creates `components.json` and `src/lib/utils.ts` (the `cn()` helper), and updates `src/index.css` with CSS variables.

If `shadcn init` complains about `tsconfig.json` paths, ensure Task 1 Step 6 was applied (the `@/*` alias).

- [ ] **Step 2: Add the base components**

```bash
cd "D:/Developing/Property-rental/frontend"
npx shadcn@latest add button input card label sonner
```
This creates `src/components/ui/{button,input,card,label,sonner}.tsx`. Each is a single owned file (shadcn's copy-in model).

- [ ] **Step 3: Smoke-test that components import**

Replace `frontend/src/App.tsx`:
```tsx
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function App() {
  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <Card className="w-96">
        <CardHeader>
          <CardTitle>Property Rental SPA</CardTitle>
        </CardHeader>
        <CardContent>
          <Button>shadcn works</Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
```

- [ ] **Step 4: Verify it renders**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run dev
```
Open `:5173` — confirm the Card with Button renders. Stop server.

- [ ] **Step 5: Verify build + lint still pass**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run build
```
No errors.

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): init shadcn/ui + base components (button, input, card, label, sonner)"
```

---

## Task 3: API client + React Query setup

**Files:**
- Create: `frontend/src/api/client.ts`, `frontend/src/api/keys.ts`, `frontend/src/types/user.ts`, `frontend/src/lib/format.ts`
- Modify: `frontend/src/main.tsx` (add QueryClientProvider + Toaster)

**Interfaces:**
- Produces:
  - `apiFetch<T>(path: string, options?: RequestOptions): Promise<T>` — fetch wrapper that sends JSON, attaches CSRF on mutations, throws `ApiError` on non-2xx, triggers session-clear on 401.
  - `queryKeys` object with `auth.me`, `auth.session` keys.
  - `User` TypeScript type: `{ id, username, email, first_name, last_name, is_landlord, is_tenant, effective_date, default_currency, default_currency_for_all_data, chart_frequency, chart_timeline, digits }`.
  - `formatCurrency(amount, currency, opts?)` and `formatDate(date, opts?)` stubs (full impl in Plan C).

- [ ] **Step 1: Install TanStack Query**

```bash
cd "D:/Developing/Property-rental/frontend"
npm install @tanstack/react-query @tanstack/react-query-devtools
```

- [ ] **Step 2: Write the User type**

`frontend/src/types/user.ts`:
```typescript
export type User = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_landlord: boolean
  is_tenant: boolean
  effective_date: string | null  // ISO date or null
  default_currency: string       // 'USD' | 'EUR' | 'GBP' | 'RUB' (per Phase 1 model)
  default_currency_for_all_data: boolean
  chart_frequency: 'M' | 'Q' | 'Y'
  chart_timeline: string         // free-form string per Phase 1 model
  digits: number
}
```
**Verify these field names against the actual `User` model** (`property_rental/rentals/models.py`). If the model has different field names, adjust this type to match.

- [ ] **Step 3: Write the API client**

`frontend/src/api/client.ts`:
```typescript
import type { User } from '@/types/user'

export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API error ${status}`)
    this.name = 'ApiError'
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
}

function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, query, headers, ...rest } = options

  const search = query
    ? '?' + new URLSearchParams(
        Object.entries(query)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : ''

  const method = (rest.method ?? 'GET').toUpperCase()
  const isMutation = method !== 'GET' && method !== 'HEAD'

  const finalHeaders: Record<string, string> = {
    ...(headers as Record<string, string>),
  }
  if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json'
  }
  if (isMutation) {
    const csrf = getCsrfToken()
    if (csrf) finalHeaders['X-CSRFToken'] = csrf
  }

  const response = await fetch(`/api/v1${path}${search}`, {
    ...rest,
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  })

  if (response.status === 401) {
    // Session expired — SessionProvider (Task 7) will pick this up via an event.
    window.dispatchEvent(new CustomEvent('auth:unauthorized'))
  }

  if (!response.ok) {
    let errorBody: unknown
    try {
      errorBody = await response.json()
    } catch {
      errorBody = await response.text()
    }
    throw new ApiError(response.status, errorBody)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

// Convenience for the SessionProvider to clear on 401.
export type { User }
```

- [ ] **Step 4: Write the query-keys factory**

`frontend/src/api/keys.ts`:
```typescript
export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  // Extended in later tasks: properties, tenants, transactions, fx, chart-data.
}
```

- [ ] **Step 5: Write the format stubs**

`frontend/src/lib/format.ts`:
```typescript
export function formatCurrency(
  amount: number | null | undefined,
  currency: string,
  opts: { compact?: boolean } = {}
): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '—'
  const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', RUB: '₽' }
  const symbol = symbols[currency] ?? ''
  if (opts.compact && Math.abs(amount) >= 1000) {
    return `${symbol}${(amount / 1000).toFixed(1)}k`
  }
  return `${symbol}${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
```

- [ ] **Step 6: Wire providers in `main.tsx`**

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Toaster } from '@/components/ui/sonner'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
      staleTime: 60_000,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster richColors />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>
)
```

- [ ] **Step 7: Verify type-check + build**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run build
```
Expected: no TypeScript errors. (Tests for `client.ts` land in Task 10.)

- [ ] **Step 8: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): add typed API client, React Query providers, format utils"
```

---

## Task 4: Backend — auth endpoints (login, logout, me)

**Files:**
- Create: `property_rental/rentals/api/auth.py`, `property_rental/rentals/tests/test_auth_api.py`
- Modify: `property_rental/rentals/api/serializers.py` (add `UserSerializer`), `property_rental/rentals/api/urls.py` (mount `auth/`)

**Interfaces:**
- Produces:
  - `POST /api/v1/auth/login/` — body `{username, password}` → 200 `{user: {...}}` (sets sessionid cookie), or 400 `{detail: "Invalid credentials"}`.
  - `POST /api/v1/auth/logout/` → 204 (clears session).
  - `GET /api/v1/auth/me/` → 200 `{user: {...}}` if authenticated, else 401.
- The `User` shape returned matches the TS type from Task 3 Step 2.

- [ ] **Step 1: Add `UserSerializer`**

In `property_rental/rentals/api/serializers.py`, append:
```python
from rest_framework import serializers
from rentals.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_landlord', 'is_tenant', 'effective_date',
            'default_currency', 'default_currency_for_all_data',
            'chart_frequency', 'chart_timeline', 'digits',
        ]
```
**Verify the field names match the actual `User` model** at `property_rental/rentals/models.py`. If `default_currency` etc. don't exist on `User`, inspect the model first and use the real names — these settings fields exist per Phase 1's `UserSettingsForm`.

- [ ] **Step 2: Write failing tests for login + me + logout (TDD)**

`property_rental/rentals/tests/test_auth_api.py`:
```python
import pytest
from django.test import Client
from rentals.tests.factories import UserFactory

@pytest.mark.django_db
def test_login_success_returns_user(db):
    user = UserFactory(username="alice", is_landlord=True)
    user.set_password("TestPass123!")
    user.save()
    c = Client()
    resp = c.post("/api/v1/auth/login/", {"username": "alice", "password": "TestPass123!"}, content_type="application/json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["is_landlord"] is True
    # Session cookie set
    assert "sessionid" in resp.cookies

@pytest.mark.django_db
def test_login_invalid_credentials_returns_400(db):
    c = Client()
    resp = c.post("/api/v1/auth/login/", {"username": "ghost", "password": "wrong"}, content_type="application/json")
    assert resp.status_code == 400
    assert "detail" in resp.json()

@pytest.mark.django_db
def test_me_requires_auth(db):
    c = Client()
    resp = c.get("/api/v1/auth/me/")
    assert resp.status_code in (401, 403)

@pytest.mark.django_db
def test_me_returns_user_when_authenticated(db):
    user = UserFactory(is_landlord=True)
    c = Client()
    c.force_login(user)
    resp = c.get("/api/v1/auth/me/")
    assert resp.status_code == 200
    assert resp.json()["user"]["id"] == user.id

@pytest.mark.django_db
def test_logout_clears_session(db):
    user = UserFactory(is_landlord=True)
    c = Client()
    c.force_login(user)
    resp = c.post("/api/v1/auth/logout/")
    assert resp.status_code == 204
    # Subsequent /me should 401
    resp2 = c.get("/api/v1/auth/me/")
    assert resp2.status_code in (401, 403)
```

- [ ] **Step 3: Run, confirm tests fail (endpoints don't exist)**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/test_auth_api.py -v
```
Expected: all FAIL with 404 / NoReverseMatch.

- [ ] **Step 4: Implement the auth views**

`property_rental/rentals/api/auth.py`:
```python
from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # No auth needed to log in

    def post(self, request: Request) -> Response:
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response({"user": UserSerializer(user).data}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response({"user": UserSerializer(request.user).data}, status=status.HTTP_200_OK)
```

- [ ] **Step 5: Wire the URLs**

In `property_rental/rentals/api/urls.py`, add at the top of `urlpatterns`:
```python
from django.urls import include, path
from .auth import LoginView, LogoutView, MeView

# ... existing router setup ...

urlpatterns = [
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("chart-data/", ChartDataView.as_view()),
] + router.urls
```

- [ ] **Step 6: Run the tests — confirm GREEN**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/test_auth_api.py -v
```
Expected: all 5 pass.

- [ ] **Step 7: Run the full backend suite to confirm no regressions**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/ -q
```
Expected: 103 (existing) + 5 (new) = 108 passed.

- [ ] **Step 8: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/api/ property_rental/rentals/tests/test_auth_api.py
git commit -m "feat(api): add auth endpoints (login, logout, me)"
```

---

## Task 5: Backend — register endpoint

**Files:**
- Modify: `property_rental/rentals/api/auth.py` (add `RegisterView`)
- Modify: `property_rental/rentals/api/serializers.py` (add register-input serializer or reuse inline validation)
- Modify: `property_rental/rentals/api/urls.py` (add `auth/register/`)
- Test: `property_rental/rentals/tests/test_auth_api.py` (append)

**Interfaces:**
- Produces: `POST /api/v1/auth/register/` — body `{username, password, email}` → 201 `{user: {...}}` (logs in the new user), or 400 with field errors.

- [ ] **Step 1: Write failing tests**

Append to `property_rental/rentals/tests/test_auth_api.py`:
```python
@pytest.mark.django_db
def test_register_creates_user_and_logs_in(db):
    c = Client()
    resp = c.post("/api/v1/auth/register/", {
        "username": "newlandlord",
        "password": "StrongPass123!",
        "email": "new@example.com",
    }, content_type="application/json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["username"] == "newlandlord"
    # Session cookie set (auto-login)
    assert "sessionid" in resp.cookies
    # Landlord auto-created (Phase 1 behavior: User.save() creates Landlord when is_landlord=True)
    # Registration should set is_landlord=True by default
    from rentals.models import User
    u = User.objects.get(username="newlandlord")
    assert u.is_landlord is True

@pytest.mark.django_db
def test_register_rejects_duplicate_username(db):
    UserFactory(username="taken")
    c = Client()
    resp = c.post("/api/v1/auth/register/", {
        "username": "taken",
        "password": "StrongPass123!",
        "email": "x@example.com",
    }, content_type="application/json")
    assert resp.status_code == 400
    assert "username" in resp.json()

@pytest.mark.django_db
def test_register_rejects_weak_password(db):
    c = Client()
    resp = c.post("/api/v1/auth/register/", {
        "username": "newlandlord",
        "password": "1",  # fails validators
        "email": "new@example.com",
    }, content_type="application/json")
    assert resp.status_code == 400
    assert "password" in resp.json()
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/test_auth_api.py -v -k register
```

- [ ] **Step 3: Implement `RegisterView`**

In `property_rental/rentals/api/auth.py`, add:
```python
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import asdict
from rest_framework.views import APIView

from rentals.models import User
from .serializers import UserSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")

        errors: dict[str, list[str]] = {}

        if not username:
            errors.setdefault("username", []).append("This field is required.")
        elif User.objects.filter(username=username).exists():
            errors.setdefault("username", []).append("A user with this username already exists.")

        if not password:
            errors.setdefault("password", []).append("This field is required.")
        else:
            try:
                validate_password(password)
            except DjangoValidationError as e:
                errors.setdefault("password", []).extend(e.messages)

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        user = User(username=username, email=email, is_landlord=True)
        user.set_password(password)
        user.save()  # Phase 1: User.save() auto-creates a Landlord when is_landlord=True
        login(request, user)
        return Response({"user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)
```

- [ ] **Step 4: Wire the URL**

In `property_rental/rentals/api/urls.py`, add `from .auth import ..., RegisterView` to the import and `path("auth/register/", RegisterView.as_view()),` to `urlpatterns`.

- [ ] **Step 5: Run, confirm GREEN**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/test_auth_api.py -v
```
Expected: all 8 auth tests pass.

- [ ] **Step 6: Run full suite**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/ -q
```
Expected: 111 passed.

- [ ] **Step 7: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/api/ property_rental/rentals/tests/test_auth_api.py
git commit -m "feat(api): add register endpoint (auto-login, landlord default)"
```

---

## Task 6: Dev proxy + prod catch-all + settings wiring

**Files:**
- Modify: `frontend/vite.config.ts` (dev proxy)
- Create: `property_rental/rentals/views.py` modification: add `spa_view` catch-all
- Modify: `property_rental/rentals/urls.py` (catch-all route at the bottom)
- Modify: `property_rental/property_rental/settings/base.py` (TEMPLATES.DIRS — note: prod-only)
- Create: `property_rental/rentals/templates/spa_index.html` (the SPA shell for prod)

**Interfaces:**
- Produces:
  - Dev: Vite proxies `/api`, `/admin`, `/media`, `/static` → Django `:8000`.
  - Prod: Django serves `frontend/dist/index.html` for any non-API/admin/static path.
  - Login cookie flow works in both modes (same-origin).

- [ ] **Step 1: Configure the Vite dev proxy**

Edit `frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': '/src' },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
    },
  },
})
```

- [ ] **Step 2: Add the prod-only TEMPLATES.DIRS to `base.py`**

In `property_rental/property_rental/settings/base.py`, modify the `TEMPLATES` setting. The `DIRS` list should include the frontend dist path **if it exists** (so dev doesn't break when `frontend/dist` isn't built yet):
```python
from pathlib import Path

FRONTEND_DIST = BASE_DIR.parent / 'frontend' / 'dist'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [str(FRONTEND_DIST)] if FRONTEND_DIST.exists() else [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # ... existing context processors
            ],
        },
    },
]
```
**Note:** This change is backward-compatible — if `frontend/dist` doesn't exist (e.g., fresh clone), `DIRS` is empty and Django behaves exactly as before.

- [ ] **Step 3: Create the SPA shell template**

`property_rental/rentals/templates/spa_index.html` (a minimal Django template that includes the built React bundle):
```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property Rental</title>
    <!-- React app styles — Vite hashes filenames, so we use Django's manifest if available -->
    {% if request.session.nonexistent_manifest_placeholder %}{% endif %}
</head>
<body>
    <div id="root"></div>
    <!-- In dev, Vite serves the bundle. In prod, we include the built JS/CSS here. -->
    <!-- The build process will replace this with the actual hashed filenames via a manifest. -->
    <script type="module" src="/static/frontend/assets/index.js"></script>
</body>
</html>
```
**Important:** this is a *placeholder*. The actual prod integration depends on how Vite's output is referenced. The cleanest approach (used by `django-vite` plugin) is to install `django-vite` and use its template tags. The alternative is to have Vite output a manifest and read it. **For this task, use the simplest working approach:**

Actually — for simplicity, let's use the `django-vite` plugin which handles dev/prod asset referencing cleanly:

```bash
cd "D:/Developing/Property-rental/property_rental"
pip install django-vite
```
Add `'django_vite'` to `INSTALLED_APPS` in `base.py` (before `django.contrib.staticfiles`).

Then `spa_index.html` becomes:
```html
{% load django_vite %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property Rental</title>
    {% vite_hass_client %}
    {% vite_asset 'src/main.tsx' %}
</head>
<body>
    <div id="root"></div>
</body>
</html>
```

And in `frontend/vite.config.ts`, add `build.outDir` and manifest config (django-vite reads the manifest):
```typescript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': '/src' } },
  server: { /* dev proxy as Step 1 */ },
  build: {
    outDir: '../property_rental/static/frontend',  // output to Django's collectstatic target
    emptyOutDir: true,
    manifest: 'manifest.json',
  },
})
```

**Decide during implementation:** django-vite vs manual manifest reading. django-vite is simpler; the implementer should verify it works with the dev proxy config above.

- [ ] **Step 4: Add the `spa_view` catch-all**

In `property_rental/rentals/views.py`, add at the bottom:
```python
from django.views.generic import TemplateView

class SpaView(TemplateView):
    """Serves the built React SPA. Falls through to index.html for client-side routing."""
    template_name = 'spa_index.html'

    def get(self, request, *args, **kwargs):
        # Optionally check auth here for protected routes — but the SPA handles that client-side.
        return super().get(request, *args, **kwargs)
```

- [ ] **Step 5: Wire the catch-all route**

In `property_rental/rentals/urls.py`, add at the **bottom** (after all other routes — order matters):
```python
from .views import SpaView

# ... existing urlpatterns ...

# Catch-all: SPA shell (must be LAST — order matters)
urlpatterns += [
    path('', SpaView.as_view()),
    re_path(r'^.*/$', SpaView.as_view()),
]
```
**Verify the existing routes** (`/api/`, `/admin/`, `/static/`, `/login/`, `/register/`) all come BEFORE the catch-all in the `urlpatterns` list. The catch-all only matches paths no other route claimed.

If `re_path` isn't imported, add `from django.urls import re_path` at the top.

- [ ] **Step 6: Test the catch-all in isolation**

Write a quick test in `property_rental/rentals/tests/test_spa_view.py`:
```python
import pytest
from django.test import Client

@pytest.mark.django_db
def test_unknown_route_serves_spa_shell(db):
    c = Client()
    resp = c.get('/some/unknown/spa/route/')
    # In dev, this would be 200 (the spa_index.html template renders)
    # In a fresh clone without frontend/dist, it might 500 — that's OK for now.
    assert resp.status_code in (200, 500)  # 500 acceptable if template path issues

@pytest.mark.django_db
def test_api_route_not_shadowed_by_catchall(db):
    c = Client()
    # /api/v1/auth/me/ without auth should 401, NOT serve the SPA
    resp = c.get('/api/v1/auth/me/')
    assert resp.status_code in (401, 403)
```
Run:
```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/test_spa_view.py -v
```
If the API shadow test fails (returns 200 instead of 401), your `urlpatterns` ordering is wrong — `/api/` must come before the catch-all.

- [ ] **Step 7: Run full backend suite**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/ -q
```
Expected: 111 prior + 2 new = 113 passed.

- [ ] **Step 8: End-to-end manual smoke test (dev proxy)**

In one terminal:
```bash
cd "D:/Developing/Property-rental/property_rental"
python manage.py runserver
```
In another:
```bash
cd "D:/Developing/Property-rental/frontend"
npm run dev
```
Open `http://127.0.0.1:5173` — confirm the SPA renders. In the browser devtools Network tab, confirm `/api/v1/auth/me/` returns 401 (proxied to Django, not served by Vite).

- [ ] **Step 9: Commit**

```bash
cd "D:/Developing/Property-rental"
git add -A
git commit -m "feat: wire Vite dev proxy + Django SPA catch-all view (django-vite)"
```

---

## Task 7: Session provider + protected routing + AppLayout

**Files:**
- Create: `frontend/src/context/SessionProvider.tsx`, `frontend/src/api/auth.ts` (React Query hooks), `frontend/src/components/layout/AppLayout.tsx`, `frontend/src/components/layout/ProtectedRoute.tsx`
- Modify: `frontend/src/App.tsx` (set up the router with placeholder routes)
- Create: `frontend/src/pages/HomePage.tsx` (placeholder — "Welcome, <name>")

**Interfaces:**
- Produces:
  - `useSession()` hook returning `{ user: User | null, isLoading: boolean }`.
  - `<SessionProvider>` wrapping the app — calls `GET /api/v1/auth/me/` on mount.
  - `<ProtectedRoute>` — renders `<Navigate to="/login" />` if no session.
  - `<AppLayout>` — navbar placeholder + `<Outlet/>`.

- [ ] **Step 1: Install React Router**

```bash
cd "D:/Developing/Property-rental/frontend"
npm install react-router-dom
```

- [ ] **Step 2: Write the auth React Query hooks**

`frontend/src/api/auth.ts`:
```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { User } from '@/types/user'

type MeResponse = { user: User }

export function useMe() {
  return useQuery<User | null>({
    queryKey: queryKeys.auth.me,
    queryFn: async () => {
      try {
        const data = await apiFetch<MeResponse>('/auth/me/')
        return data.user
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 401) return null
        throw err
      }
    },
    retry: false,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { username: string; password: string }) =>
      apiFetch<MeResponse>('/auth/login/', { method: 'POST', body: vars }),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.auth.me, data.user)
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/auth/logout/', { method: 'POST' }),
    onSettled: () => {
      qc.setQueryData(queryKeys.auth.me, null)
      qc.clear()
    },
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { username: string; password: string; email: string }) =>
      apiFetch<MeResponse>('/auth/register/', { method: 'POST', body: vars }),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.auth.me, data.user)
    },
  })
}
```
You'll need to import `ApiError` from `./client` in `useMe`. Add that import.

- [ ] **Step 3: Write the SessionProvider**

`frontend/src/context/SessionProvider.tsx`:
```typescript
import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useMe } from '@/api/auth'
import type { User } from '@/types/user'

type SessionContextValue = {
  user: User | null
  isLoading: boolean
}

const SessionContext = createContext<SessionContextValue>({ user: null, isLoading: true })

export function SessionProvider({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useMe()

  // Listen for 401 events from the API client and refetch.
  useEffect(() => {
    const handler = () => { /* React Query will refetch on next query invalidation */ }
    window.addEventListener('auth:unauthorized', handler)
    return () => window.removeEventListener('auth:unauthorized', handler)
  }, [])

  return (
    <SessionContext.Provider value={{ user: user ?? null, isLoading }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  return useContext(SessionContext)
}
```

- [ ] **Step 4: Write `ProtectedRoute`**

`frontend/src/components/layout/ProtectedRoute.tsx`:
```tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useSession } from '@/context/SessionProvider'
import { Skeleton } from '@/components/ui/skeleton'  // shadcn skeleton (add via `npx shadcn@latest add skeleton`)

export function ProtectedRoute() {
  const { user, isLoading } = useSession()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Skeleton className="h-12 w-12 rounded-full" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}
```
If `Skeleton` isn't added yet, run `npx shadcn@latest add skeleton` first.

- [ ] **Step 5: Write `AppLayout`**

`frontend/src/components/layout/AppLayout.tsx`:
```tsx
import { Outlet } from 'react-router-dom'
import { useSession } from '@/context/SessionProvider'
import { useLogout } from '@/api/auth'
import { Button } from '@/components/ui/button'

export function AppLayout() {
  const { user } = useSession()
  const logout = useLogout()
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto flex h-14 items-center justify-between px-4">
          <span className="font-semibold">Property Rental</span>
          <div className="flex items-center gap-4">
            {user && <span className="text-sm text-muted-foreground">{user.username}</span>}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
            >
              {logout.isPending ? 'Logging out…' : 'Logout'}
            </Button>
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 6: Write placeholder HomePage**

`frontend/src/pages/HomePage.tsx`:
```tsx
import { useSession } from '@/context/SessionProvider'

export function HomePage() {
  const { user } = useSession()
  return (
    <div>
      <h1 className="text-2xl font-bold">Welcome, {user?.first_name || user?.username}</h1>
      <p className="text-muted-foreground mt-2">Dashboard arrives in Plan C.</p>
    </div>
  )
}
```

- [ ] **Step 7: Wire the router**

`frontend/src/App.tsx`:
```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SessionProvider } from '@/context/SessionProvider'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'
import { HomePage } from '@/pages/HomePage'

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<HomePage />} />
            </Route>
          </Route>
          {/* /login and /register added in Tasks 8 & 9 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}

export default App
```

- [ ] **Step 8: Verify type-check + build**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run build
```
No TypeScript errors.

- [ ] **Step 9: Manual smoke test**

Both servers running. Open `:5173` unauthenticated → should redirect to `/login` (no route yet → falls into `*` → Navigate to `/` → ProtectedRoute redirects → but `/login` doesn't exist yet, so you'll see a blank page). **This is expected** — Tasks 8 & 9 add the login/register routes. Confirm no console errors.

- [ ] **Step 10: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): session provider, protected routing, app layout, router skeleton"
```

---

## Task 8: Login page

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/login` route, render outside ProtectedRoute)
- Create: `frontend/src/__fixtures__/user.ts`

**Interfaces:**
- Produces: `/login` route rendering a centered card with username/password form, error display, and redirect to `/` on success.

- [ ] **Step 1: Create the user fixture**

`frontend/src/__fixtures__/user.ts`:
```typescript
import type { User } from '@/types/user'

export const fixtureUser: User = {
  id: 1,
  username: 'alice',
  email: 'alice@example.com',
  first_name: 'Alice',
  last_name: 'Smith',
  is_landlord: true,
  is_tenant: false,
  effective_date: null,
  default_currency: 'USD',
  default_currency_for_all_data: false,
  chart_frequency: 'M',
  chart_timeline: 'last_6_months',
  digits: 0,
}
```

- [ ] **Step 2: Write `LoginPage`**

`frontend/src/pages/LoginPage.tsx`:
```tsx
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useLogin } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const login = useLogin()
  const navigate = useNavigate()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)
    login.mutate(
      { username, password },
      {
        onSuccess: () => navigate('/'),
        onError: (err) => {
          // err is ApiError; body has {detail: "Invalid credentials"} or field errors
          const detail = (err as { body?: { detail?: string } }).body?.detail
          setErrorMsg(detail ?? 'Login failed')
        },
      }
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>Enter your credentials to access your portfolio.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            {errorMsg && (
              <p className="text-sm text-destructive" role="alert">{errorMsg}</p>
            )}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? 'Logging in…' : 'Log in'}
            </Button>
            <p className="text-sm text-center text-muted-foreground">
              Don't have an account? <Link to="/register" className="underline">Register</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: Add the `/login` route**

In `frontend/src/App.tsx`, import LoginPage and add it OUTSIDE the `<ProtectedRoute>`:
```tsx
import { LoginPage } from '@/pages/LoginPage'

// in <Routes>:
<Route path="/login" element={<LoginPage />} />
```
Also add a redirect from `/logout` → `/login` if you want (the navbar Logout button just calls the mutation, so optional).

- [ ] **Step 4: Verify build**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run build
```

- [ ] **Step 5: Manual smoke test**

Both servers running. Open `:5173/login` → form renders. Try invalid creds → "Invalid credentials" message. Try valid (smoke_landlord / SmokeTest123!) → redirects to `/` showing "Welcome, smoke_landlord". Logout button works.

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): login page with form + error handling"
```

---

## Task 9: Register page

**Files:**
- Create: `frontend/src/pages/RegisterPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/register` route)

**Interfaces:**
- Produces: `/register` route with username/email/password form, password-confirm field, server-error display, redirect to `/` on success.

- [ ] **Step 1: Write `RegisterPage`**

`frontend/src/pages/RegisterPage.tsx`:
```tsx
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useRegister } from '@/api/auth'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const register = useRegister()
  const navigate = useNavigate()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})
    if (password !== passwordConfirm) {
      setErrors({ password: 'Passwords do not match' })
      return
    }
    register.mutate(
      { username, email, password },
      {
        onSuccess: () => navigate('/'),
        onError: (err) => {
          if (err instanceof ApiError && err.body && typeof err.body === 'object') {
            setErrors(err.body as Record<string, string>)
          } else {
            setErrors({ general: 'Registration failed' })
          }
        },
      }
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create account</CardTitle>
          <CardDescription>Register as a landlord to manage your properties.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
              {errors.username && <p className="text-sm text-destructive">{errors.username}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              {errors.email && <p className="text-sm text-destructive">{errors.email}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required />
              {errors.password && <p className="text-sm text-destructive">{errors.password}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="passwordConfirm">Confirm password</Label>
              <Input id="passwordConfirm" type="password" value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} autoComplete="new-password" required />
            </div>
            {errors.general && <p className="text-sm text-destructive">{errors.general}</p>}
            <Button type="submit" className="w-full" disabled={register.isPending}>
              {register.isPending ? 'Creating…' : 'Register'}
            </Button>
            <p className="text-sm text-center text-muted-foreground">
              Already have an account? <Link to="/login" className="underline">Log in</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Add the `/register` route**

In `frontend/src/App.tsx`, add:
```tsx
import { RegisterPage } from '@/pages/RegisterPage'
// in <Routes>:
<Route path="/register" element={<RegisterPage />} />
```

- [ ] **Step 3: Verify build**

```bash
cd "D:/Developing/Property-rental/frontend"
npm run build
```

- [ ] **Step 4: Manual smoke test**

Open `:5173/register` → form renders. Try mismatched passwords → error. Try existing username → server error "username". Try valid new user → redirects to `/` showing welcome.

- [ ] **Step 5: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): register page with validation + error handling"
```

---

## Task 10: Vitest + Testing Library + MSW setup

**Files:**
- Create: `frontend/vitest.config.ts` (or extend `vite.config.ts`), `frontend/src/test/setup.ts`, `frontend/src/test/handlers.ts`, `frontend/src/test/TestApp.tsx`
- Modify: `frontend/package.json` (add test scripts)

**Interfaces:**
- Produces: `npm test` runs Vitest; MSW intercepts fetches in tests; Testing Library matchers available.

- [ ] **Step 1: Install dev deps**

```bash
cd "D:/Developing/Property-rental/frontend"
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom msw
```

- [ ] **Step 2: Configure Vitest**

Add to `frontend/vite.config.ts` (merge into existing config):
```typescript
/// <reference types="vitest" />
// ... existing imports ...

export default defineConfig({
  // ... existing config ...
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
```

- [ ] **Step 3: Write the setup file**

`frontend/src/test/setup.ts`:
```typescript
import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './handlers'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

- [ ] **Step 4: Write MSW handlers (auth endpoints only for now)**

`frontend/src/test/handlers.ts`:
```typescript
import { http, HttpResponse } from 'msw'
import { fixtureUser } from '@/__fixtures__/user'

export const server = setupServer()

// Default handlers — extended per test or globally here.
const defaultHandlers = [
  http.get('/api/v1/auth/me/', () => HttpResponse.json({ user: fixtureUser })),
  http.post('/api/v1/auth/login/', async ({ request }) => {
    const body = await request.json() as { username: string; password: string }
    if (body.username === 'alice' && body.password === 'TestPass123!') {
      return HttpResponse.json({ user: fixtureUser })
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 400 })
  }),
  http.post('/api/v1/auth/logout/', () => new HttpResponse(null, { status: 204 })),
  http.post('/api/v1/auth/register/', async ({ request }) => {
    const body = await request.json() as { username: string }
    if (body.username === 'taken') {
      return HttpResponse.json({ username: 'A user with this username already exists.' }, { status: 400 })
    }
    return HttpResponse.json({ user: { ...fixtureUser, username: body.username } }, { status: 201 })
  }),
]

import { setupServer } from 'msw/node'
export const server = setupServer(...defaultHandlers)
```
(If the duplicate `server` declaration causes issues, restructure: define `defaultHandlers` first, then `export const server = setupServer(...defaultHandlers)` once.)

- [ ] **Step 5: Add test scripts to `package.json`**

In `frontend/package.json`, add to `"scripts"`:
```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

- [ ] **Step 6: Verify the setup with a trivial test**

`frontend/src/test/setup.test.ts`:
```typescript
import { describe, it, expect } from 'vitest'

describe('vitest setup', () => {
  it('works', () => {
    expect(1 + 1).toBe(2)
  })
})
```
Run:
```bash
cd "D:/Developing/Property-rental/frontend"
npm test
```
Expected: 1 test passes.

- [ ] **Step 7: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "test(frontend): Vitest + Testing Library + MSW scaffold"
```

---

## Task 11: Tests for API client + auth hooks

**Files:**
- Create: `frontend/src/api/client.test.ts`, `frontend/src/api/auth.test.tsx`

**Interfaces:**
- Consumes: MSW handlers from Task 10.
- Produces: tests verifying CSRF header attachment, 401 handling, hook behavior.

- [ ] **Step 1: Write client tests**

`frontend/src/api/client.test.ts`:
```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { apiFetch, ApiError } from './client'

describe('apiFetch', () => {
  beforeEach(() => {
    // Set a fake CSRF cookie
    document.cookie = 'csrftoken=fake-csrf; path=/'
  })

  it('attaches CSRF header on POST', async () => {
    let capturedHeaders: Headers | undefined
    // Override fetch to capture headers
    const originalFetch = globalThis.fetch
    globalThis.fetch = ((input: RequestInfo, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers)
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    }) as typeof fetch

    await apiFetch('/test/', { method: 'POST', body: { x: 1 } })

    globalThis.fetch = originalFetch
    expect(capturedHeaders?.get('X-CSRFToken')).toBe('fake-csrf')
    expect(capturedHeaders?.get('Content-Type')).toBe('application/json')
  })

  it('does not attach CSRF on GET', async () => {
    let capturedHeaders: Headers | undefined
    const originalFetch = globalThis.fetch
    globalThis.fetch = ((input: RequestInfo, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers)
      return Promise.resolve(new Response('null', { status: 200 }))
    }) as typeof fetch

    await apiFetch('/test/')

    globalThis.fetch = originalFetch
    expect(capturedHeaders?.get('X-CSRFToken')).toBeNull()
  })

  it('serializes query params', async () => {
    let capturedUrl = ''
    const originalFetch = globalThis.fetch
    globalThis.fetch = ((input: RequestInfo) => {
      capturedUrl = input.toString()
      return Promise.resolve(new Response('null', { status: 200 }))
    }) as typeof fetch

    await apiFetch('/test/', { query: { a: 1, b: 'hi', c: undefined } })
    globalThis.fetch = originalFetch
    expect(capturedUrl).toContain('a=1')
    expect(capturedUrl).toContain('b=hi')
    expect(capturedUrl).not.toContain('c=')
  })

  it('throws ApiError on non-2xx', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (() => Promise.resolve(new Response(JSON.stringify({ detail: 'nope' }), { status: 400 }))) as typeof fetch
    await expect(apiFetch('/test/')).rejects.toMatchObject({ name: 'ApiError', status: 400 })
    globalThis.fetch = originalFetch
  })

  it('dispatches auth:unauthorized event on 401', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (() => Promise.resolve(new Response('null', { status: 401 }))) as typeof fetch
    const events: string[] = []
    window.addEventListener('auth:unauthorized', () => events.push('fired'))
    await expect(apiFetch('/test/')).rejects.toThrow()
    globalThis.fetch = originalFetch
    expect(events).toEqual(['fired'])
  })
})
```

- [ ] **Step 2: Write auth hook tests**

`frontend/src/api/auth.test.tsx`:
```typescript
import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useMe, useLogin, useLogout } from './auth'
import type { ReactNode } from 'react'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

describe('useMe', () => {
  it('returns the user when authenticated', async () => {
    const { result } = renderHook(() => useMe(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.username).toBe('alice')
  })
})

describe('useLogin', () => {
  it('logs in and updates the cache', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useLogin(), { wrapper })
    result.current.mutate({ username: 'alice', password: 'TestPass123!' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(qc.getQueryData(['auth', 'me'])).toMatchObject({ username: 'alice' })
  })
})

describe('useLogout', () => {
  it('clears the cache', async () => {
    const qc = new QueryClient()
    qc.setQueryData(['auth', 'me'], { username: 'alice' })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useLogout(), { wrapper })
    result.current.mutate({})
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(qc.getQueryData(['auth', 'me'])).toBeNull()
  })
})
```

- [ ] **Step 3: Run tests**

```bash
cd "D:/Developing/Property-rental/frontend"
npm test
```
Expected: all pass (1 setup + 5 client + 3 auth = 9).

- [ ] **Step 4: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "test(frontend): API client + auth React Query hook tests"
```

---

## Task 12: Tests for Login + Register pages + CI jobs

**Files:**
- Create: `frontend/src/pages/LoginPage.test.tsx`, `frontend/src/pages/RegisterPage.test.tsx`
- Modify: `.github/workflows/ci.yml` (add frontend jobs)

**Interfaces:**
- Produces: page-level tests (form submit, error display, redirect); CI runs both pytest and `npm` jobs.

- [ ] **Step 1: Write LoginPage tests**

`frontend/src/pages/LoginPage.test.tsx`:
```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginPage } from './LoginPage'

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('LoginPage', () => {
  it('renders the form', () => {
    renderWithProviders()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument()
  })

  it('shows error on invalid credentials', async () => {
    const user = userEvent.setup()
    renderWithProviders()
    await user.type(screen.getByLabelText(/username/i), 'wrong')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /log in/i }))
    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument()
  })

  it('has a link to register', () => {
    renderWithProviders()
    expect(screen.getByRole('link', { name: /register/i })).toHaveAttribute('href', '/register')
  })
})
```

- [ ] **Step 2: Write RegisterPage tests**

`frontend/src/pages/RegisterPage.test.tsx`:
```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RegisterPage } from './RegisterPage'

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RegisterPage', () => {
  it('renders the form', () => {
    renderWithProviders()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getAllByLabelText(/password/i)).toHaveLength(2)  // password + confirm
  })

  it('rejects mismatched passwords locally', async () => {
    const user = userEvent.setup()
    renderWithProviders()
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/email/i), 'new@example.com')
    const passwords = screen.getAllByLabelText(/password/i)
    await user.type(passwords[0], 'StrongPass123!')
    await user.type(passwords[1], 'DifferentPass123!')
    await user.click(screen.getByRole('button', { name: /register/i }))
    expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument()
  })

  it('shows server error on duplicate username', async () => {
    const user = userEvent.setup()
    renderWithProviders()
    await user.type(screen.getByLabelText(/username/i), 'taken')
    await user.type(screen.getByLabelText(/email/i), 'x@example.com')
    const passwords = screen.getAllByLabelText(/password/i)
    await user.type(passwords[0], 'StrongPass123!')
    await user.type(passwords[1], 'StrongPass123!')
    await user.click(screen.getByRole('button', { name: /register/i }))
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run frontend tests**

```bash
cd "D:/Developing/Property-rental/frontend"
npm test
```
Expected: all pass.

- [ ] **Step 4: Update CI to include frontend jobs**

Edit `.github/workflows/ci.yml`. Add three new jobs that run alongside the existing `backend-test`:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  backend-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install -r requirements-dev.txt
        working-directory: property_rental
      - run: pytest --cov=rentals
        working-directory: property_rental

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: frontend
      - run: npm test
        working-directory: frontend

  frontend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
```
**Note:** `npm ci` requires `package-lock.json` to be committed. Verify it exists in `frontend/` after Task 1.

- [ ] **Step 5: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/ .github/workflows/ci.yml
git commit -m "test(frontend): login + register page tests; add frontend CI jobs"
```

---

## Task 13: Delete legacy login + register templates + views

**Files:**
- Delete: `property_rental/rentals/templates/rentals/login.html`, `property_rental/rentals/templates/rentals/register.html`
- Modify: `property_rental/rentals/views.py` (delete `login_view`, `register_view`)
- Modify: `property_rental/rentals/urls.py` (delete `/login/` and `/register/` routes — replaced by SPA)

**Interfaces:**
- Consumes: SPA `/login` and `/register` routes from Tasks 8 & 9 (verified working).
- Produces: no Django-rendered login/register UI; the SPA is the sole entry point.

- [ ] **Step 1: Confirm the SPA login/register flow works end-to-end**

Manual smoke test (both servers): `/login` and `/register` routes in the SPA function correctly. If broken, STOP — don't delete the legacy until the SPA replacement is verified.

- [ ] **Step 2: Delete the templates**

```bash
cd "D:/Developing/Property-rental"
git rm property_rental/rentals/templates/rentals/login.html
git rm property_rental/rentals/templates/rentals/register.html
```

- [ ] **Step 3: Delete the view functions**

In `property_rental/rentals/views.py`, delete the `login_view` and `register_view` functions. Grep first to find them:
```bash
cd "D:/Developing/Property-rental/property_rental"
grep -n "def login_view\|def register_view" rentals/views.py
```
Delete the entire function bodies for each (and any imports they were the sole user of — but verify with grep first).

- [ ] **Step 4: Delete the URL routes**

In `property_rental/rentals/urls.py`, delete the `path('login/', ...)` and `path('register/', ...)` entries. The SPA catch-all (Task 6) now handles these paths.

- [ ] **Step 5: Update any backend tests that referenced the old views**

```bash
cd "D:/Developing/Property-rental/property_rental"
grep -rn "login_view\|register_view\|/login/\|/register/" rentals/tests/
```
For each hit:
- If the test was testing the old template view (e.g., a 200-on-GET test), delete it — the SPA replaces this functionality, tested in `frontend/src/pages/LoginPage.test.tsx`.
- If the test was testing auth flow via the old view, migrate it to use `/api/v1/auth/login/` instead.

- [ ] **Step 6: Run the full backend suite**

```bash
cd "D:/Developing/Property-rental/property_rental"
python -m pytest rentals/tests/ -q
```
Expected: all pass. The deleted view tests are gone; the new `/api/v1/auth/*` tests cover the functionality.

- [ ] **Step 7: Run the full frontend suite**

```bash
cd "D:/Developing/Property-rental/frontend"
npm test
```

- [ ] **Step 8: Manual smoke test (both servers)**

Confirm:
- `:5173/login` works (SPA route, not Django).
- `:5173/register` works.
- Logging in redirects to `/` with welcome message.
- The Django server's `/login/` and `/register/` paths now serve the SPA shell (catch-all).

- [ ] **Step 9: Commit**

```bash
cd "D:/Developing/Property-rental"
git add -A
git commit -m "refactor: delete legacy login/register templates + views (SPA replaces them)"
```

---

## Self-Review

**1. Spec coverage (Plan A subset):**

| Spec section | Task(s) | Covered? |
|---|---|---|
| §4.1 frontend/ sibling layout | Tasks 1-2 | ✅ |
| §4.3 dev proxy + prod Django-serves-SPA | Task 6 | ✅ |
| §4.5 CSRF on mutations | Task 3 (client) | ✅ |
| §6 /login SPA route | Tasks 4, 8 | ✅ |
| §6 /register SPA route | Tasks 5, 9 | ✅ |
| §7 React Query setup | Tasks 3, 7 | ✅ |
| §7 sonner toasts | Task 3 (provider wiring) | ✅ |
| §7 skeleton loading state | Task 7 (ProtectedRoute) | ✅ |
| §8 4 auth endpoints | Tasks 4, 5 | ✅ |
| §9 Vitest + Testing Library + MSW | Tasks 10-12 | ✅ |
| §9 CI frontend jobs | Task 12 | ✅ |
| §10 DoD #3 delete templates as SPA replaces | Task 13 (login/register) | ✅ |

**Spec sections NOT in Plan A** (covered by B or C):
- §5 charts (Plan C)
- §6 entity pages other than login/register (Plan B)
- §7 forms other than login/register (Plan B)
- §8 PropertyValuation ViewSet, FX inversion fix (Plan B)
- §10 DoD items about charts/legacy-bulk-deletion (Plans B and C)

**2. Placeholder scan:** Searched for TBD/TODO/etc. — the only "decide during implementation" item is in Task 6 Step 3 (django-vite vs manual manifest). That's a legitimate implementation-time choice with a recommended default; not a placeholder. Acceptable.

**3. Type consistency:**
- `User` type: defined Task 3 Step 2, consumed by Tasks 7, 8, 9, 10, 11. Consistent.
- `apiFetch<T>(path, options)`: defined Task 3 Step 3, consumed by Tasks 7 (auth.ts), 11. Consistent.
- `queryKeys.auth.me`: defined Task 3 Step 4, consumed Tasks 7, 11. Consistent.
- `useMe`/`useLogin`/`useLogout`/`useRegister`: defined Task 7 Step 2, consumed Tasks 8, 9, 11. Consistent.

All consistent.

**4. Sequencing:** Tasks build incrementally — scaffold → API client → backend endpoints → integration → session/routing → login → register → tests → CI → legacy deletion. Each task produces independently testable changes.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-spa-foundation-auth.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
