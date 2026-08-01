# Property rental tracking application

This application tracks rental-property operations and investment performance. Django and Django REST Framework provide the backend and typed analytics API; the frontend is a React/TypeScript SPA built with Vite, TanStack Query, Tailwind CSS, shadcn/ui, and Recharts.

## Distinctiveness and Complexity
+ The idea of the project is to bring property portfolio management analytics to the database of properties
+ The data is structured as a comprehensive database consisting of eight models (users, landlord, tenants, property, property funding, transactions, rent history, FX data)
+ The app allows registered user to save own properties and include key information (address, footage, rooms, price, etc.), create tenants and "rent" own properties to tenants. Include revenue inputs (rent received) and costs (utility bills, capex, etc.) into the respective database. And track the economics of each property project: P&L components, charges executed in time, rent outstanding
+ Recharts renders the typed investment dashboard, property valuation history, and tenant rent-performance analytics
+ Instances of the main models (user, property, tenant, transaction) can also be edited or deleted in case of the wrong data present
+ User settings include editable Rent preferences such as default currency, chart frequency, chart timeline and number of digits shown in tables. In production, username, name, email, passwords, MFA, passkeys and application roles are owned by centralized Life OS identity and synchronized into Rent read-only.
+ The application is multi-currency. Each property has its own _natural_ currency. Data representation can be shown in a user-selected reporting currency, and the home page summarizes portfolio statistics in the default currency. In production, FX acquisition is performed by the scheduled `refresh_fx` management command; ordinary web requests and financial writes do not call external FX providers.
+ For consistency of FX conversions _Bellman-Ford_ algorithm used for shortest path cross-currency conversion using `networkx` library to deal with undirected graphs
+ Local development can use a per-user effective-date override for deterministic analytics. Production disables this developer override and resolves reports using the configured business timezone.

## File structure
`Property_rental` build with Django with the single app `rentals`. Rentals app has fairly standard structure:
+ `migrations` folder keep the history of model updates
+ `frontend` contains the React/TypeScript SPA, component tests, and Playwright scenarios
+ `rentals/analytics` owns financial classification, FX conversion, occupancy, yields, and bounded date bucketing
+ Django templates provide only the SPA shell; behavioral endpoints live under `/api/v1/`
+ In addition, `forms.py` handles form creation, `constants.py` centralizes model/form constants, and `utils.py` plus `rentals/services/` provide currency formatting, analytics helpers, and scheduled FX refresh support.

### Running the application

Use `uv` for the backend environment. Backend dependencies live in
`pyproject.toml` and are locked in `uv.lock`; the old
`property_rental/requirements.txt` workflow is no longer used.

Backend, from PowerShell:

```powershell
cd D:\Developing\Property-rental
uv sync --group dev

uv run python property_rental\manage.py migrate
uv run python property_rental\manage.py runserver
```

Frontend, in a second terminal:

```powershell
cd D:\Developing\Property-rental\frontend
npm ci
npm run dev
```

Open the Django app at `http://127.0.0.1:8000`. In development,
`django-vite` loads the React bundle from the Vite dev server.

Backend checks:

```powershell
cd D:\Developing\Property-rental
uv run pytest -q
uv run python property_rental\manage.py check
```

Frontend checks:

```powershell
cd D:\Developing\Property-rental\frontend
npm test
npm run lint
npm run build
```

### Production container and Life OS handoff

The application is prepared for Life OS deployment at `https://rent.linik.ru`.
The repository provides the production image, strict environment contract,
PostgreSQL settings, Authentik OIDC integration boundary, health endpoints, and
one-shot operational commands. It does not deploy to the VPS and does not create
production PostgreSQL, Traefik, Authentik, or backup infrastructure.

Key handoff documents:

+ `docs/deployment/life-os.md` — production runtime contract, required
  environment variables, networks, OIDC groups, health checks, security, FX
  scheduling, and static asset behavior.
+ `docs/deployment/sqlite-migration.md` — temporary `import_sqlite` workflow,
  reconciliation rules, and explicit OIDC identity-linking procedure.
+ `docs/deployment/backup-restore.md` — persistent data and restore notes.
+ `docs/deployment/image-report.md` — measured image size and largest layers.

Build and smoke-test the production image locally:

```powershell
docker build --tag property-rental:life-os .
python scripts/container_smoke.py --image property-rental:life-os
```

Merged `main` builds are published for deployment as immutable GHCR tags:

```text
ghcr.io/lym-afla/property-rental:sha-<full-commit-sha>
```

Life OS should deploy the full SHA tag or digest, never `latest`.

Run migrations as an explicit one-shot job, never as implicit web-container
startup work:

```powershell
python property_rental\manage.py migrate --noinput
```

Production settings require `DATABASE_URL` to be PostgreSQL and fail startup
when required production configuration is missing.

### Analytics API and visual regression checks

The React investment dashboard reads typed analytics responses from `/api/v1/analytics/portfolio/summary/`, `cash-flow/`, `expenses/`, `profit-loss/`, `property-contribution/`, `yields/`, `property-breakdown/`, and `occupancy/`. Property breakdown reports each property's server-calculated value, debt, or equity history in the selected reporting currency. Gross yield is annualized gross rental income divided by the latest property value; equity yield is annualized rental income net of costs divided by equity (latest property value less latest debt). Property valuation history is available at `/api/v1/analytics/properties/<id>/valuation/`. Time-series requests are capped at 600 buckets.

Run the frontend checks from `frontend/`:

```powershell
npm ci
$env:PW_CHANNEL='chrome'
npm run test:e2e -- --workers=1
```

`test:e2e` starts Vite with a root base for deterministic fixture-backed Playwright tests and runs the desktop (1440px), tablet (768px), and mobile (390px) projects. Exact-pixel baselines are pinned to Windows Chrome locally and in CI; other platform/browser combinations skip only the visual snapshot spec. Update intentional baselines with `$env:PW_CHANNEL='chrome'; npm run test:e2e -- --update-snapshots --workers=1`.
