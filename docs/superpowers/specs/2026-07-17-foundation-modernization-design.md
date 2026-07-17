# Foundation Modernization — Design Spec

**Date:** 2026-07-17
**Status:** Approved (pending user review of written spec)
**Phase:** 1 of 4
**Predecessors:** none
**Successors:** Phase 2 (Charting overhaul), Phase 3 (Frontend reshape / React SPA), Phase 4 (Architecture debt)

---

## 1. Context

The Property-rental app is a Django 4.2.4 monolith (`rentals` app) on SQLite, deployed to PythonAnywhere, with Bootstrap 5 + vanilla JS + jQuery + Chart.js templates. An audit identified security holes, fat views, an N+1-style FX-conversion bottleneck, no tests, and uncontrolled configuration. The app is **personal / not live**, so we can reshape freely and break things.

The full modernization is four phases:

| Phase | Sub-project | Spec status |
|---|---|---|
| **1** | **Foundation** (this document) | designing |
| 2 | Charting overhaul (Recharts rebuild) | future spec |
| 3 | Frontend reshape (React + shadcn/ui SPA) | future spec |
| 4 | Architecture debt (god-model refactor, full coverage) | future spec |

**Strategic direction (decided):** Django + DRF backend, React + TypeScript + Vite + shadcn/ui + Recharts frontend, Postgres. Sequencing: thin Foundation first, then charting, then broad frontend, then remaining architecture debt. Existing SQLite data is to be **migrated** (not disposed of).

This phase delivers the security fixes, a service layer, Postgres, a DRF skeleton, a test scaffold, and the FX graph cache. It does **not** introduce React or touch the chart UI — those land in later phases.

## 2. Goals

1. Close every security hole identified in the audit (IDOR, missing auth, global state, settings hygiene).
2. Extract business logic from `views.py` (1120 lines) into a `rentals/services/` package so views become thin HTTP adapters.
3. Cache the FX conversion graph so it is built once per request (not once per transaction row).
4. Migrate from SQLite to Postgres with a verified, repeatable migration script.
5. Stand up a real DRF API (`/api/v1/`) with typed serializers — the foundation Phase 2's charting consumes.
6. Establish a test scaffold with **characterization tests** that pin current behavior of all financial calculations *before* any refactor touches them.

## 3. Non-Goals (out of scope for this phase)

- React, Vite, shadcn/ui — Phase 3.
- Chart redesign, new chart types, Chart.js → Recharts — Phase 2. (The `/api/v1/chart-data/` endpoint lands here, but no chart UI changes.)
- `Tenant` god-model refactor and `debt` / `debt_advance_payment` dedup — Phase 4. We move the logic into a service but do not redesign it.
- Removal of jQuery / DataTables — Phase 3.
- Token/JWT auth — Phase 3 (SessionAuthentication for now).
- Migrating every existing template endpoint to DRF — only the endpoints needed for Phase 2 (chart-data) plus a clean pattern others can follow.

## 4. Design

### 4.1 Security fixes

These are non-negotiable and ship together as the first mergeable unit.

| Fix | Location | Action |
|---|---|---|
| **DELETE IDOR** | `rentals/views.py:616-618` (`handle_element` DELETE branch) | Add the same ownership check used by GET/PUT: `if element.owned_by.user != request.user: return 403`. Add a characterization test asserting landlord B cannot delete landlord A's entity. |
| **Missing auth** | `update_date` (:818), `update_fx_view` (:1097), `property_choices` (:798), `chart_data_request` (:840), `new_form` (:282), `fx_list` (:1071) | Add `@login_required` (or DRF permission classes once migrated). |
| **`update_fx_view` scope** | `views.py:1097-1112` | Currently iterates **every** `Property` across all users. Restrict to `Property.objects.filter(owned_by__user=request.user)`. |
| **Global as-of date** | `rentals/utils.py:10` (`effective_current_date`), `update_date` view, navbar date picker in `layout.html:57-58` | Remove the module-level global. Add `User.effective_date` field (nullable, defaults to today). Replace `effective_current_date` reads with `request.user.effective_date`. Remove the navbar date picker and its route. |
| **`SECRET_KEY`** | `property_rental/settings.py:24` | Read from env; **raise on missing in production** (no insecure fallback). Dev may use a fixed dev key from `dev.py`. |
| **`DEBUG`** | `settings.py:28` | Default `False`. Only `True` when explicitly set via env in `dev.py`. |
| **`ALLOWED_HOSTS`** | `settings.py:30` | Read from env. Remove hardcoded `lymafla.pythonanywhere.com`. |
| **Settings split** | `settings.py` (single file, gitignored at `.gitignore:19`) | Split into `settings/base.py`, `settings/dev.py`, `settings/prod.py`. **Remove the `.gitignore:19` entry** so settings are version-controlled. `DJANGO_SETTINGS_MODULE` selects dev vs prod. |
| **Password validators** | `settings.py:94-107` | Uncomment `UserAttributeAttributeValidator`, `MinimumLengthValidator`, `CommonPasswordValidator`. |
| **CDN SRI** | `layout.html:10-11`, `index.html:90-91`, `properties.html:174-175`, `tenants.html:79-80` | Add `integrity=` + `crossorigin="anonymous"` to every CDN `<script>`/`<link>`. (Phase 3 will vendor these via the build step; SRI is the interim mitigation.) |

### 4.2 Service layer extraction

New package `rentals/services/` (a directory, made an app-less module under `rentals/`). Views become thin HTTP adapters: parse request → call service → return response.

```
rentals/services/
├── __init__.py
├── fx.py            # FX rate fetching + cross-currency conversion (with graph cache)
├── financials.py    # P&L calc, transaction aggregation, currency-conversion helpers
├── charts.py        # get_chart_data (returns typed dicts; later Pydantic schemas)
└── scheduler.py     # month-by-month debt / grace-period calculation
```

**Module responsibilities:**

- **`fx.py`** — Absorbs the logic currently in `FX.update_fx_rates()` and `FX.get_rate()` (`models.py:481-591`). The `networkx.Graph` is built **once** and cached as a module-level attribute with an invalidation hook (rebuilt only when an `FX` row is added/changed, or on TTL expiry). Exposes `convert(amount, from_currency, to_currency, as_of)` and `get_rate(from_currency, to_currency, as_of)`. The `FX` model becomes a thin data model; its classmethods delegate here.

> **Plan amendment (2026-07-17):** Before the FX cache lands, the `FX` table is migrated from its current wide format (one `DecimalField` column per currency pair — `EURUSD`, `GBPUSD`, `USDRUB`) to normalized long format (`from_currency`, `to_currency`, `rate`, `date`). The wide format is an anti-pattern: adding a currency pair requires a schema migration, and `FX.get_rate` must introspect `_meta.fields` and parse column names at runtime to discover graph edges. Long format makes a new pair a row insert (no migration) and collapses the graph-builder loop to a plain `for fx in FX.objects.filter(...): g.add_edge(fx.from_currency, fx.to_currency, weight=fx.rate)`. The migration is value-preserving and gated by the Task 4 FX characterization tests — every `get_rate` output must be unchanged. This is captured in the plan as a dedicated task sequenced after the char tests and before the FX cache.

- **`financials.py`** — Absorbs `pnl_calc` (`views.py:997-1051`), the aggregation loop in `Transaction.financials` (`models.py:402-456`), and the four duplicated Python currency-conversion loops (in `financials`, `rent_total`, `pnl_calc`, `table_data`). One canonical `convert_transactions(transactions_qs, target_currency, as_of)` helper. `Transaction.financials` becomes a thin wrapper calling the service.

- **`charts.py`** — Absorbs `get_chart_data` (`views.py:871-993`). Returns a typed dict (or dataclass) consumed by both the DRF endpoint and the existing template-render path. As part of the move, the **hardcoded `property_valuation` parameters** (`views.py:1066` — frequency `'M'`, dates `'2022-06-01'`/`'2023-09-15'`, currency `'USD'`) are replaced by values passed from the request.

- **`scheduler.py`** — Absorbs the month-by-month debt/grace-period loop currently in `Tenant.debt` (`models.py:180-263`) and `Tenant.debt_advance_payment` (`:266-363`). **No dedup in this phase** — both functions move verbatim (Phase 4 will unify them). `Tenant.debt()` becomes a thin delegate.

**Guardrails:**

- Characterization tests for each financial calculation are written **before** the corresponding extraction (see §4.5). The refactor is purely mechanical: move logic, keep behavior, run tests, repeat.
- Models retain simple derived properties and fields. Complex orchestration lives in services.
- No new features. No bug fixes beyond the items explicitly listed (the `aspectRatio` bug, the `property_valuation` hardcoding, the `calculate_from_date` `months=` bug). These are in scope as they surface during extraction.

**Bugs to fix on contact during extraction:**

| Bug | Location | Fix |
|---|---|---|
| `calculate_from_date` invalid `date.replace(months=...)` | `utils.py:255` (YTD branch) | Use `relativedelta(months=1)` (already a dependency). |
| `property_valuation` hardcoded params | `views.py:1066` | Use request/session-provided params. |
| `match data_type` without `case _:` | `views.py:432` (`handle_element` outer match) | Add a default returning 404 or 400. |

The `aspectRatio: 1|3` chart typo is **not** fixed here — it is deferred to Phase 2 (see §8), where the Chart.js UI is replaced wholesale by Recharts.

### 4.3 Postgres migration

- Add `psycopg[binary]` (v3) to `requirements.txt`. Configure `DATABASES` for Postgres in `settings/prod.py`.
- `settings/dev.py` may keep SQLite for local dev convenience (developer's choice during implementation; either is acceptable).
- **Migration script** at `scripts/migrate_sqlite_to_postgres.py`:
  - Opens a read connection to the existing `db.sqlite3` via a second Django connection (or raw `sqlite3`).
  - For each model, bulk-inserts rows into Postgres in transaction batches.
  - Verifies row counts per table match before and after.
  - Idempotent-ish: detects already-migrated tables and skips.
  - Prints a per-table summary; exits non-zero on any mismatch.
- Run once against the real DB; retire SQLite from version control afterwards (keep `db.sqlite3` in `.gitignore`).

### 4.4 DRF skeleton + typed API

- DRF is already a dependency (`djangorestframework==3.14.0`) but only `ModelSerializer` is used. Upgrade to `APIView` / `ViewSet` with proper permission classes.
- New URL namespace `/api/v1/` under `rentals/urls.py`.
- **Endpoints in scope for this phase:**
  - `/api/v1/properties/` — list/create/retrieve/update/destroy (`ModelViewSet`).
  - `/api/v1/tenants/`, `/api/v1/transactions/` — same.
  - `/api/v1/fx/` — list rates + `POST refresh/` (auth-scoped to the requesting user).
  - **`/api/v1/chart-data/`** — the keystone for Phase 2. Accepts `(type, id, frequency, start, end, currency)` and returns the chart payload from `services/charts.py`. GET with query params. Auth required.
- Serializers: one `ModelSerializer` per entity. `chart-data` returns a typed dict via a small response serializer (or dataclass-as-dict for now).
- **Auth:** `SessionAuthentication` only. Per-user queryset filtering in `get_queryset()` (every list endpoint filters by `owned_by__user=request.user`), so the IDOR class of bug is structurally impossible in the API layer.
- Existing template-rendered endpoints stay working during this phase (no big-bang cutover). They can be removed once Phase 3's React UI replaces them.

### 4.5 Test scaffold

- **Remove `.gitignore:14-16`** entries (`property_rental/tests/`, `test_*.py`, `testing.py`) so tests are tracked.
- Add to `requirements.txt` (or a separate `requirements-dev.txt`): `pytest`, `pytest-django`, `factory-boy`, `coverage`.
- Config: `pyproject.toml` with `[tool.pytest.ini_options]` (`DJANGO_SETTINGS_MODULE=property_rental.settings.dev`, `python_files=["tests.py","test_*.py"]`).
- Tests live under `rentals/tests/` (split by area: `tests/test_security.py`, `tests/test_financials.py`, `tests/test_fx.py`, `tests/test_charts.py`, `tests/test_api.py`).
- **Characterization tests first** — before extracting or refactoring any calculation, write a test that pins its current output on a known input. Targets:
  - `Tenant.debt(...)` for several tenant scenarios (in arrears, in grace, advance payment).
  - `Tenant.rent_total(...)` same-currency and cross-currency.
  - `Transaction.financials(...)` aggregation.
  - `FX.get_rate(...)` for direct and multi-hop conversions.
  - `pnl_calc(...)` for a sample portfolio.
  - `get_chart_data(...)` for each of homePage / property / tenant.
  - These golden tests are the safety net for the service-layer extraction and the FX cache change.
- **New-code tests:** every security fix (§4.1) has an asserting test. Every DRF endpoint (§4.4) has at least one happy-path and one auth-failure test.
- **CI:** `.github/workflows/ci.yml` running `pytest --cov` on push and PR. Matrix: Python 3.11, 3.12.

### 4.6 Settings reorganization

```
property_rental/settings/
├── __init__.py
├── base.py     # shared: INSTALLED_APPS, MIDDLEWARE, TEMPLATES, LANGUAGE_CODE, etc.
├── dev.py      # DEBUG=True, SQLite, weak SECRET_KEY allowed
└── prod.py     # DEBUG=False, Postgres, SECRET_KEY from env (raise if missing), ALLOWED_HOSTS from env
```

`manage.py` and `wsgi.py` default to `property_rental.settings.dev` and `property_rental.settings.prod` respectively (or selected via `DJANGO_SETTINGS_MODULE` env var). The single-file `settings.py` is removed.

## 5. Verification (definition of done)

Phase 1 is complete when **all** of the following hold:

1. **Security:** each of the 5 security items has a passing test proving the fix (e.g., landlord B gets 403 on landlord A's DELETE; unauthenticated request to `update_fx` gets 401/302; `manage.py check --deploy` reports no `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` critical warnings).
2. **Services:** `views.py` has shed ≥300 lines (target: under ~800). All four service modules exist and are imported by the views/models that previously held the logic.
3. **FX cache:** a benchmark (ad-hoc script or test) demonstrates the FX graph is built ≤1 time per request, not once per transaction row. The characterization test for `FX.get_rate` still passes (output unchanged).
4. **Postgres:** `scripts/migrate_sqlite_to_postgres.py` runs cleanly against the real SQLite DB and per-table row counts match. Postgres is the configured prod DB.
5. **API:** `/api/v1/chart-data/` returns the same payload shape as the existing `get_chart_data` for at least homePage / property / tenant types (characterization test). All endpoints enforce per-user querysets.
6. **Tests:** characterization test suite passes on the original SQLite DB **before** the refactor (green baseline) and on Postgres **after** (green migrated). CI workflow exists and is green on `main`.
7. **Settings:** `settings.py` removed; `settings/{base,dev,prod}.py` exist and are version-controlled. `.gitignore:19` entry for settings removed.
8. **No regressions:** existing Django template pages still render and behave identically (manual smoke test of home / properties / tenants / transactions / FX pages).

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Service extraction changes financial output silently | Characterization tests pin every calc before any move; CI gates every PR. |
| FX cache returns stale rates after an `FX` row is added | Cache invalidation hook: `FX.save()` and `FX.delete()` clear the cache. Add a test asserting a freshly-added rate is visible. |
| Postgres migration loses or duplicates rows | Migration script verifies row counts; idempotent re-run; tested against a copy first. |
| Removing global as-of date breaks workflows that relied on it | The behavior was already buggy (cross-user bleed); the per-user field is strictly better. Document the change in commit message. |
| Settings split breaks PythonAnywhere deployment | Document the `DJANGO_SETTINGS_MODULE` change for the deploy target in the commit and README. |

## 7. Open questions

None blocking. (During implementation, the developer may choose SQLite-vs-Postgres for `dev.py` and the exact batch size in the migration script — both are local decisions.)

## 8. Out-of-phase bug register

Bugs discovered during the audit but explicitly deferred to later phases (so they are not lost):

| Bug | Phase | Note |
|---|---|---|
| `aspectRatio: 1\|3` bitwise-OR typo (`index.html:107`) | Phase 2 | Will be replaced wholesale by Recharts rebuild. |
| Property valuation chart never refreshes after edits | Phase 2 | Addressed in the chart overhaul. |
| Currency axis label `$k` confusion | Phase 2 | Revisited in chart redesign. |
| `Tenant.debt` / `debt_advance_payment` duplication | Phase 4 | Logic moves in this phase but is not unified. |
| Dead code: `properties_not used.js`, orphaned `settings.html`, commented blocks in `layout.js`/`element.js` | Phase 3 | Cleaned during frontend reshape. |
| Unused deps: `peewee`, `bs4`/`lxml` (if confirmed unused) | Phase 1 ( opportunistic ) | Safe to remove in this phase if a grep confirms no imports. |
| 29 stray `print()` statements | Phase 1 ( opportunistic ) | Replace with `logging` or remove during service extraction. |
