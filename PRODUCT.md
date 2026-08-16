# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is the owner-operator tracking their own rental portfolio (personal Life OS deployment at `rent.linik.ru`). Other registered-user capability exists, but those accounts are occasional or trusted ones — not the audience design work should optimize for. The product is a personal operator tool, not a multi-tenant SaaS.

## Product Purpose

Rent tracks rental-property operations and investment performance. The operator records properties (address, footage, rooms, price), creates tenants, rents properties to them, and enters revenue (rent received) and costs (utility bills, capex, etc.). The product then shows the economics of each property project: P&L components, charges executed over time, and rent outstanding.

The primary job is **operational bookkeeping** — tracking rent received, charges, and outstanding rent per tenant is the core; the investment dashboard, valuation history, and yield analytics are the reporting layer on top. Success means the operator's records are complete and current, and the numbers derived from them are trustworthy.

## Positioning

Portfolio-level analytics over a structured rental database:

- Eight-model data core (users, landlord, tenants, property, property funding, transactions, rent history, FX data) instead of a generic ledger.
- Multi-currency by design: every property keeps its own natural currency; reporting happens in a user-selected currency; cross-currency conversion uses Bellman-Ford shortest paths over the FX-rate graph (`networkx`) so derived figures stay consistent.
- Deep integration with the centralized Life OS identity (Authentik OIDC): usernames, emails, credentials, MFA, and roles are owned centrally and synchronized into Rent read-only.

## Operating Context

- Production runs at `https://rent.linik.ru` as part of the Life OS ecosystem: Docker image, PostgreSQL, Traefik, gunicorn; identity via Authentik OIDC.
- Identity and application roles are owned by Life OS; Rent treats them as read-only. Logout and session lifecycle are bound to the OIDC session.
- FX rates in production are acquired only by the scheduled `refresh_fx` management command, which back-fills missing historical pairs for dated rental records; ordinary web requests and financial writes never call external FX providers.
- Reports resolve in the configured business timezone. Local development may use a per-user effective-date override for deterministic analytics; production disables it.
- User preferences include default currency, chart frequency, chart timeline, and number of digits shown in tables.
- Local development: `uv` for the Django backend, `npm` + Vite for the SPA (loaded via `django-vite`), SQLite locally and PostgreSQL in production.

## Capabilities and Constraints

- Full CRUD on the main instances (user, property, tenant, transaction) for correcting wrong data.
- Dashboard analytics rendered with Recharts: cumulative cash, expense drivers, net cash flow, occupancy risk, property contribution, portfolio breakdown, revenue/expense trend, yield comparison; per-property valuation history; per-tenant rent performance.
- Behavioral API lives under `/api/v1/` (typed DRF endpoints); Django templates provide only the SPA shell.
- Analytics (financial classification, FX conversion, occupancy, yields, bounded date bucketing) is owned by the backend `rentals/analytics` module; the SPA renders typed responses.
- Production deploys as immutable GHCR image tags (`sha-<full-commit-sha>`), never `latest`.

## Brand Commitments

- Product name: **Rent**, deployed at `rent.linik.ru` as part of Life OS.
- No other voice, logo, or identity constraints have been declared binding.

## Evidence on Hand

- `README.md` — product description, architecture, run/test commands, deployment handoff.
- `docs/deployment/life-os.md` — production runtime contract (environment, networks, OIDC groups, health checks, FX scheduling).
- `docs/deployment/sqlite-migration.md`, `docs/deployment/backup-restore.md`, `docs/deployment/image-report.md` — operational workflows.
- No testimonials, customers, benchmarks, or marketing claims exist; future work must not fabricate them.

## Product Principles

1. **Bookkeeping first.** Capturing rent, charges, and costs quickly and correctly is the primary job; analytics is the reporting layer that serves it, never the reverse.
2. **Numbers must be trustworthy.** FX conversion, P&L, and outstanding-rent math stay deterministic and auditable; the UI presents derived figures, it never invents them.
3. **One operator, zero friction.** Optimize for the owner's recurring review flow over onboarding strangers or marketing surfaces.
4. **Respect the currency of record.** Every property keeps its natural currency; the reporting currency is a lens, never a mutation.
5. **Life OS is the boundary.** Identity, credentials, and roles belong to the central system; Rent stays read-only toward them.

## Accessibility & Inclusion

Sensible web-accessibility defaults apply (contrast, keyboard operability, readable charts and tables); no formal compliance standard is currently required.
