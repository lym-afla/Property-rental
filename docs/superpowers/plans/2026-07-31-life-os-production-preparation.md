# Life OS Production Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible, non-root Property Rental production image and application-side Life OS contract with PostgreSQL-only production settings, Authentik OIDC, scheduled deterministic FX refresh, safe SQLite import, health endpoints, CI coverage, and measured image size.

**Architecture:** One Gunicorn/Django container serves the DRF API and build-time-compiled React SPA through WhiteNoise. Production uses a required PostgreSQL `DATABASE_URL`, application-native OIDC with PKCE and bounded authorization age, explicit migration/import/FX jobs, and two external Life OS networks without repository-owned production infrastructure.

**Tech Stack:** Python 3.11, Django 4.2, Django REST Framework, mozilla-django-oidc 5.0.2, psycopg 3, Gunicorn, WhiteNoise, uv/uv.lock, React 19, Vite 8, Node 20 builder, Debian Python slim, PostgreSQL, GitHub Actions.

## Global Constraints

- Preserve existing rental ownership, analytics behavior, frontend behavior, and tests except where production-only password authentication and effective-date controls are intentionally disabled.
- Production must require PostgreSQL and must never fall back to SQLite.
- Production must not create PostgreSQL, Traefik, Authentik, another frontend server, Redis, Celery, or any other infrastructure service.
- OIDC must enable PKCE with `OIDC_USE_PKCE=True` and `OIDC_PKCE_CODE_CHALLENGE_METHOD="S256"`.
- Durable identity is the database-unique `(issuer, subject)` pair; email and username are mutable profile attributes.
- Every protected request must enforce the configured authorization age; failed mutations are never automatically replayed.
- Ordinary web requests and financial writes must perform no external FX calls.
- Docker runtime performs no migration, dependency install, frontend build, or `collectstatic` operation.
- Docker's Node stage runs only `npm ci` and `npm run build`; tests and lint remain CI jobs outside the image build.
- The final image runs Python 3.11 as non-root and contains no Node/npm/uv/toolchain/cache/SQLite/source-map/test/Playwright/secret artifacts.
- Do not modify or deploy the Life OS infrastructure repository.

---

## File Structure

New focused modules keep settings, identity, request authorization, health, migration, and FX concerns independent:

- `property_rental/property_rental/settings/env.py`: strict environment parsing and PostgreSQL URL conversion.
- `property_rental/property_rental/settings/build.py`: deterministic, offline static collection settings.
- `property_rental/property_rental/settings/test_postgres.py`: CI PostgreSQL test settings.
- `property_rental/rentals/oidc.py`: custom claim-to-local-user binding, callback bookkeeping, and logout URL behavior.
- `property_rental/rentals/middleware.py`: maximum authorization-age enforcement for every protected request.
- `property_rental/rentals/health.py`: liveness and readiness views.
- `property_rental/rentals/management/commands/import_sqlite.py`: temporary transactional importer.
- `property_rental/rentals/management/commands/link_oidc_identity.py`: deliberate post-import issuer/subject linkage.
- `property_rental/rentals/management/commands/refresh_fx.py`: scheduled deterministic refresh entry point.
- `property_rental/rentals/services/fx_refresh.py`: provider-independent refresh orchestration and reporting.
- `property_rental/gunicorn.conf.py`: production server lifecycle/logging configuration.
- `scripts/container_smoke.py`: runtime and content assertions used by CI.
- `Dockerfile`, `.dockerignore`, `.env.production.example`: image and deployment interface.
- `docs/deployment/life-os.md`, `docs/deployment/sqlite-migration.md`, `docs/deployment/backup-restore.md`, `docs/deployment/image-report.md`: handoff and evidence.

---

### Task 1: Lock Production Dependencies and Strict Settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `property_rental/property_rental/settings/env.py`
- Create: `property_rental/property_rental/settings/build.py`
- Create: `property_rental/property_rental/settings/test_postgres.py`
- Modify: `property_rental/property_rental/settings/base.py`
- Modify: `property_rental/property_rental/settings/prod.py`
- Test: `property_rental/rentals/tests/test_production_settings.py`

**Interfaces:**
- Produces: `required_env(name: str) -> str`, `csv_env(name: str) -> list[str]`, `postgres_database(url: str) -> dict[str, object]`.
- Produces: production `DATABASES`, OIDC settings, proxy/cookie/header settings, and build-safe static settings used by later tasks.

- [ ] **Step 1: Write failing settings tests**

Add tests that import production settings in a subprocess with controlled environment variables and assert: missing `DATABASE_URL` fails; `sqlite:///...` fails; `postgresql://user:pass@db:5432/rental` resolves to Django's PostgreSQL backend; `DEBUG` cannot be enabled; hosts/origins are parsed without empty entries; PKCE is true/S256; proxy, cookie, HSTS, referrer, and no-CORS contracts are present. Add a build-settings test that imports without database/OIDC secrets and fails when the Vite manifest is absent.

- [ ] **Step 2: Verify the settings tests fail for the missing strict configuration**

Run: `uv run pytest property_rental/rentals/tests/test_production_settings.py -q`

Expected: failures show absent `env.py`/`build.py`, non-URL database configuration, and missing OIDC/PKCE settings.

- [ ] **Step 3: Pin runtime dependencies and regenerate the lock**

Add exact direct dependencies `gunicorn==23.0.0` and `mozilla-django-oidc==5.0.2`. Use `uv lock`, then prove the production selection with `uv sync --frozen --no-dev --no-editable` in a disposable environment or the later Docker builder.

- [ ] **Step 4: Implement strict environment parsing and settings separation**

Implement PostgreSQL URL parsing with Django-compatible `ENGINE`, `NAME`, `USER`, `PASSWORD`, `HOST`, `PORT`, and connection health checks; accept `postgres://` and `postgresql://` only. Build settings use a non-secret ephemeral value solely because Django requires `SECRET_KEY` at import time, never serialize it, and validate `rentals/static/frontend/manifest.json` plus the `src/main.tsx` entry before collection. Production requires every approved configuration variable, fixes `DEBUG=False`, sets `SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')`, and adds no CORS package or headers.

- [ ] **Step 5: Run focused settings and deploy checks**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_production_settings.py -q
$env:DJANGO_SETTINGS_MODULE='property_rental.settings.prod'
$env:DATABASE_URL='postgresql://rental:secret@postgres:5432/rental'
$env:DJANGO_SECRET_KEY='test-only-runtime-value'
$env:DJANGO_ALLOWED_HOSTS='rent.linik.ru'
$env:DJANGO_CSRF_TRUSTED_ORIGINS='https://rent.linik.ru'
$env:BUSINESS_TIME_ZONE='Europe/Moscow'
$env:OIDC_ISSUER='https://auth.linik.ru/application/o/rent/'
$env:OIDC_CLIENT_ID='rent-test'
$env:OIDC_CLIENT_SECRET='test-only'
$env:OIDC_CALLBACK_URL='https://rent.linik.ru/oidc/callback/'
$env:OIDC_LOGOUT_URL='https://auth.linik.ru/application/o/rent/end-session/'
uv run python property_rental/manage.py check --deploy
```

Expected: tests pass; deploy check has no security warnings attributable to application settings. A database connection is not required by `check --deploy`.

- [ ] **Step 6: Commit the settings boundary**

```powershell
git add pyproject.toml uv.lock property_rental/property_rental/settings property_rental/rentals/tests/test_production_settings.py
git commit -m "feat: add strict production configuration"
```

---

### Task 2: Add Durable OIDC Identity and Claim Binding

**Files:**
- Modify: `property_rental/rentals/models.py`
- Create: `property_rental/rentals/migrations/0023_oidc_identity.py`
- Create: `property_rental/rentals/oidc.py`
- Modify: `property_rental/property_rental/settings/base.py`
- Modify: `property_rental/property_rental/settings/prod.py`
- Modify: `property_rental/property_rental/urls.py`
- Test: `property_rental/rentals/tests/test_oidc.py`

**Interfaces:**
- Produces: `OIDCIdentity(user, issuer, subject)` with `OneToOneField(User)` and `UniqueConstraint(fields=('issuer', 'subject'))`.
- Produces: `RentalOIDCAuthenticationBackend.verify_claims(claims: dict) -> bool` and `filter_users_by_claims(claims: dict) -> QuerySet[User]`/`create_user(claims: dict) -> User` overrides limited to binding and claims.
- Produces: `mark_session_authorized(request, groups: Collection[str]) -> None` storing an ISO timestamp and authorized groups only after viewer validation.

- [ ] **Step 1: Write failing model and backend tests**

Cover database rejection of duplicate `(issuer, subject)`, rejection of a second identity for one user, lookup by issuer/subject despite changed email/username, denial without `lifeos:app:rent:viewer`, creation without a usable password, no email-only account merge, and `last_authorized_at` update only after valid viewer claims. Patch the base backend only at the protocol boundary; assertions target the subclass's binding behavior rather than token cryptography.

- [ ] **Step 2: Verify OIDC tests fail**

Run: `uv run pytest property_rental/rentals/tests/test_oidc.py -q`

Expected: failures show missing model/backend/routes and absent claim enforcement.

- [ ] **Step 3: Implement the identity migration and narrow backend**

Add immutable issuer/subject fields, database constraints, admin-safe string representation, and a subclass of `mozilla_django_oidc.auth.OIDCAuthenticationBackend`. Delegate signature/audience/nonce/token handling to `super()`. Normalize the configured issuer only according to exact issuer semantics, require the configured groups-claim name, and refuse identity inference from profile fields.

- [ ] **Step 4: Wire OIDC routes and settings**

Add `mozilla_django_oidc` to installed apps, the base OIDC backend plus development-only `ModelBackend` selection, `/oidc/` URLs, PKCE settings, allowed redirect host, scopes, RS256/JWKS/discovery-derived endpoints as supported by the pinned library, and callback/logout behavior. Keep access/id tokens out of the Django session unless the library requires a short-lived ID token for provider logout; document any required storage explicitly.

- [ ] **Step 5: Verify OIDC behavior and migrations**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_oidc.py -q
uv run python property_rental/manage.py makemigrations --check --dry-run
uv run python property_rental/manage.py migrate
```

Expected: tests pass, no uncommitted model changes, migration applies.

- [ ] **Step 6: Commit durable identity**

```powershell
git add property_rental/rentals/models.py property_rental/rentals/migrations/0023_oidc_identity.py property_rental/rentals/oidc.py property_rental/property_rental/settings property_rental/property_rental/urls.py property_rental/rentals/tests/test_oidc.py
git commit -m "feat: bind users to Authentik OIDC subjects"
```

---

### Task 3: Enforce Authorization Renewal on Every Request

**Files:**
- Create: `property_rental/rentals/middleware.py`
- Modify: `property_rental/property_rental/settings/base.py`
- Modify: `property_rental/property_rental/settings/prod.py`
- Modify: `property_rental/rentals/api/auth.py`
- Modify: `property_rental/rentals/api/urls.py`
- Modify: `property_rental/rentals/admin.py`
- Test: `property_rental/rentals/tests/test_oidc_authorization.py`

**Interfaces:**
- Produces: `AuthorizationAgeMiddleware(get_response)` that checks `request.session['last_authorized_at']` before protected views.
- Produces: JSON refresh response `{ "code": "authorization_refresh_required", "refresh_url": "...", "retry": false }` for unsafe methods, with status 403.
- Consumes: `SessionRefresh` 403/`refresh_url` behavior for eligible GET/XHR.

- [ ] **Step 1: Write failing authorization-age tests**

Test fresh sessions, five-minute-expired GET/XHR, expired POST/PATCH/DELETE rejected before a sentinel view mutates state, missing viewer group, successful renewed callback timestamp update, group revocation clearing the session, exempt health/OIDC/static routes, safe `next` URLs, and admin denial without `lifeos:app:rent:admin` even when `is_staff=True`.

- [ ] **Step 2: Verify failures**

Run: `uv run pytest property_rental/rentals/tests/test_oidc_authorization.py -q`

Expected: failures prove stale mutation requests currently reach views and admin currently trusts local staff alone.

- [ ] **Step 3: Implement request middleware and admin authorization**

Place application authorization middleware after Django authentication and in the correct order relative to `SessionRefresh`. Calculate age from timezone-aware timestamps, use the configured 300-second default, reject unsafe methods without invoking the downstream view, and clear invalid sessions. Restrict exemptions to explicit OIDC callback/authenticate, health, and static paths.

- [ ] **Step 4: Production-disable local password flows**

Gate login, register, and change-password URLs behind `LOCAL_PASSWORD_AUTH_ENABLED`, false and startup-rejected in production. Keep logout and `me` session APIs. Require the admin group in an admin-site permission hook or middleware that cannot be bypassed by local `is_staff`.

- [ ] **Step 5: Verify renewal and legacy development auth**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_oidc_authorization.py property_rental/rentals/tests/test_auth_api.py -q
```

Expected: renewal tests pass; existing development password-auth tests remain green under development settings.

- [ ] **Step 6: Commit request authorization**

```powershell
git add property_rental/rentals/middleware.py property_rental/property_rental/settings property_rental/rentals/api property_rental/rentals/admin.py property_rental/rentals/tests/test_oidc_authorization.py
git commit -m "feat: enforce bounded OIDC authorization age"
```

---

### Task 4: Make the React Session Flow OIDC-Aware and Remove Production Developer Controls

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/context/SessionProvider.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/pages/RegisterPage.tsx`
- Modify: `frontend/src/pages/ProfilePage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/types/user.ts`
- Modify: `property_rental/rentals/api/serializers.py`
- Test: `frontend/src/api/client.test.ts`
- Test: `frontend/src/pages/LoginPage.test.tsx`
- Test: `frontend/src/pages/ProfilePage.test.tsx`
- Test: `property_rental/rentals/tests/test_auth_api.py`

**Interfaces:**
- Consumes: OIDC entry URL and refresh responses from Tasks 2-3.
- Produces: `startAuthorizationRefresh(refreshUrl: string): void` using top-level `window.location.assign` and never replaying the failed request.

- [ ] **Step 1: Write failing frontend and API tests**

Assert a `403` refresh response navigates the top-level browser once, the original mutation fetch is called exactly once, no automatic retry occurs after navigation, production login renders an SSO action rather than a password form, registration route is unavailable in production mode, and effective date is absent from production profile serialization and form controls.

- [ ] **Step 2: Verify focused failures**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_auth_api.py -q
Push-Location frontend; npm test -- --run src/api/client.test.ts src/pages/LoginPage.test.tsx src/pages/ProfilePage.test.tsx; Pop-Location
```

Expected: tests fail on replay/redirect behavior and existing production-visible local controls.

- [ ] **Step 3: Implement OIDC navigation and production feature flags**

Handle the defined response shape centrally in `apiFetch`, preserving the original local URL in the OIDC authenticate URL. Do not call `fetch` again. Render a single Authentik sign-in action when production configuration injected into the SPA shell disables local auth. Remove registration links/routes and password controls in that mode while retaining development behavior.

- [ ] **Step 4: Isolate effective-date behavior**

Make the serializer omit/reject `effective_date` updates in production and use the configured business timezone's current date for production calculations. Preserve explicit bounded analytics query ranges and development characterization coverage.

- [ ] **Step 5: Run frontend/backend auth suites**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_auth_api.py property_rental/rentals/tests/test_security.py -q
Push-Location frontend; npm test -- --run src/api/client.test.ts src/pages/LoginPage.test.tsx src/pages/ProfilePage.test.tsx; npm run lint; Pop-Location
```

Expected: all focused tests and lint pass.

- [ ] **Step 6: Commit client authentication behavior**

```powershell
git add frontend/src property_rental/rentals/api/serializers.py property_rental/rentals/tests
git commit -m "feat: integrate SPA with OIDC session renewal"
```

---

### Task 5: Add Exact Health Semantics and Production Server Configuration

**Files:**
- Create: `property_rental/rentals/health.py`
- Modify: `property_rental/property_rental/urls.py`
- Create: `property_rental/gunicorn.conf.py`
- Test: `property_rental/rentals/tests/test_health.py`

**Interfaces:**
- Produces: `liveness(request) -> JsonResponse` with no DB/external access.
- Produces: `readiness(request) -> JsonResponse` using `SELECT 1` on Django's default connection.
- Produces: Gunicorn config reading `PORT`, logging to `-`, and using graceful timeout settings.

- [ ] **Step 1: Write failing health tests**

Patch Django's connection cursor to raise and assert `/health/live` still returns 200 while `/health/ready` returns 503 with a generic body. Assert readiness returns 200 after `SELECT 1`, both endpoints permit anonymous access, and neither invokes FX/OIDC code.

- [ ] **Step 2: Verify health failures**

Run: `uv run pytest property_rental/rentals/tests/test_health.py -q`

Expected: 404 failures for both endpoints.

- [ ] **Step 3: Implement health views and Gunicorn config**

Return compact JSON and disable caching. Use `connections['default'].cursor().execute('SELECT 1')` only in readiness. Set Gunicorn bind to `0.0.0.0:${PORT:-8000}`, access/error logs to stdout/stderr, a documented worker count default, `graceful_timeout`, and temporary directory `/tmp`.

- [ ] **Step 4: Verify health and URL precedence**

Run: `uv run pytest property_rental/rentals/tests/test_health.py property_rental/rentals/tests/test_spa_view.py -q`

Expected: health routes do not fall through to the SPA and all tests pass.

- [ ] **Step 5: Commit runtime endpoints**

```powershell
git add property_rental/rentals/health.py property_rental/property_rental/urls.py property_rental/gunicorn.conf.py property_rental/rentals/tests/test_health.py
git commit -m "feat: add production health and server configuration"
```

---

### Task 6: Replace the SQLite Copier with a Safe Temporary Import Workflow

**Files:**
- Create: `property_rental/rentals/management/commands/import_sqlite.py`
- Create: `property_rental/rentals/management/commands/link_oidc_identity.py`
- Delete: `property_rental/rentals/management/commands/migrate_sqlite_to_postgres.py`
- Delete: `property_rental/scripts/migrate_sqlite_to_postgres.py`
- Replace: `property_rental/rentals/tests/test_migration_command.py`
- Create: `property_rental/rentals/tests/test_link_oidc_identity.py`

**Interfaces:**
- Produces: `import_sqlite --source PATH [--report PATH] [--dry-run]`.
- Produces: `link_oidc_identity --user-id ID --issuer ISSUER --subject SUBJECT`, refusing ambiguous/conflicting linkage.
- Produces: reconciliation JSON with `source_count`, `destination_count`, `status`, relationship errors, and sequence status per model.

- [ ] **Step 1: Write failing importer contract tests**

Create a migrated temporary SQLite source fixture with representative users/ownership/FX rows. Test that business-table emptiness ignores Django system rows, non-empty/conflicting business data fails, imports are atomic, primary/foreign keys survive, passwords become unusable, PostgreSQL sequence-reset SQL is requested, exact reruns report reconciled without inserting, partial reruns fail, and report counts/relationships are deterministic. Mark PostgreSQL-specific cases for the CI backend.

- [ ] **Step 2: Verify importer tests fail against the legacy command**

Run: `uv run pytest property_rental/rentals/tests/test_migration_command.py property_rental/rentals/tests/test_link_oidc_identity.py -q`

Expected: failures show legacy count-only idempotency, usable password preservation, no sequence reconciliation, and no deliberate identity-link command.

- [ ] **Step 3: Implement transactional import**

Read source tables through a read-only SQLite URI, validate columns against the supported schema, wrap all destination writes in `transaction.atomic()`, import dependency order with explicit IDs, call Django `sequence_reset_sql`, validate ownership/FKs and counts, disable passwords with `set_unusable_password()`, and serialize the reconciliation report. Never run `migrate` inside this command.

- [ ] **Step 4: Implement deliberate OIDC linkage**

Require explicit user ID, issuer, and subject. Refuse an already-linked user, an existing `(issuer, subject)`, unknown user, or profile-based lookup. Create the row atomically and print only non-secret identifiers needed for audit.

- [ ] **Step 5: Verify importer on SQLite unit coverage and PostgreSQL integration coverage**

Run: `uv run pytest property_rental/rentals/tests/test_migration_command.py property_rental/rentals/tests/test_link_oidc_identity.py -q`

Expected: all backend-independent cases pass locally; PostgreSQL-marked sequence/integration cases pass in the CI PostgreSQL job.

- [ ] **Step 6: Commit temporary migration tooling**

```powershell
git add property_rental/rentals/management property_rental/rentals/tests/test_migration_command.py property_rental/rentals/tests/test_link_oidc_identity.py property_rental/scripts/migrate_sqlite_to_postgres.py
git commit -m "feat: make SQLite import safe and auditable"
```

---

### Task 7: Separate and Harden Scheduled FX Refresh

**Files:**
- Modify: `property_rental/rentals/models.py`
- Create: `property_rental/rentals/migrations/0024_fx_rate_identity.py`
- Create: `property_rental/rentals/services/fx_refresh.py`
- Create: `property_rental/rentals/management/commands/refresh_fx.py`
- Modify: `property_rental/rentals/api/views.py`
- Modify: `property_rental/rentals/api/urls.py`
- Modify: `property_rental/rentals/utils.py`
- Test: `property_rental/rentals/tests/test_fx_refresh.py`
- Modify: `property_rental/rentals/tests/test_api.py`

**Interfaces:**
- Produces: unique FX identity `(date, from_currency, to_currency)` with canonical uppercase ordered representation defined by the service.
- Produces: `refresh_rates(*, as_of: date, pairs: Collection[CurrencyPair], provider: RateProvider) -> RefreshReport`.
- Produces: report buckets `cached`, `fetched`, `unavailable`, `invalid`; command exits nonzero for unavailable/invalid required rates.

- [ ] **Step 1: Write failing deterministic refresh tests**

Test duplicate identity rejection, canonical pair normalization, cached rows avoiding provider calls, idempotent reruns, invalid/non-positive/non-finite provider values, bounded provider errors retaining existing rows, unavailable reporting, timezone-derived business date, and no external provider invocation from transaction create/update or any API endpoint.

- [ ] **Step 2: Verify failures and characterize current synchronous behavior**

Run: `uv run pytest property_rental/rentals/tests/test_fx_refresh.py property_rental/rentals/tests/test_api.py -q`

Expected: new tests fail because the API still exposes synchronous refresh and provider/report abstractions do not exist.

- [ ] **Step 3: Implement persistence constraint and refresh service**

Add the database constraint after a data migration that canonicalizes/reconciles any reverse/duplicate rows without discarding valid data. Define a provider protocol, validate returned rates before atomic upsert, use explicit HTTP/provider time bounds supported by yfinance or a bounded adapter, and preserve valid cached data on all failure paths.

- [ ] **Step 4: Add scheduled command and remove web-provider calls**

Implement date/pair arguments, business-timezone default date, structured stdout report, and `CommandError` for unavailable/invalid required rates. Remove the `/api/v1/fx/update/` action and ensure transaction writes never call `update_rates`; retain read-only FX freshness data needed by the UI.

- [ ] **Step 5: Verify FX and analytics behavior**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_fx_refresh.py property_rental/rentals/tests/test_services.py property_rental/rentals/tests/test_fx_char.py property_rental/rentals/tests/test_analytics_api.py property_rental/rentals/tests/test_api.py -q
uv run python property_rental/manage.py makemigrations --check --dry-run
```

Expected: deterministic refresh and existing conversion/analytics tests pass; no pending migration.

- [ ] **Step 6: Commit scheduled FX architecture**

```powershell
git add property_rental/rentals/models.py property_rental/rentals/migrations property_rental/rentals/services property_rental/rentals/management/commands/refresh_fx.py property_rental/rentals/api property_rental/rentals/utils.py property_rental/rentals/tests
git commit -m "feat: move FX acquisition to scheduled refresh"
```

---

### Task 8: Build the Minimal Production Image and Runtime Audit

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `.env.production.example`
- Create: `scripts/container_smoke.py`
- Modify: `frontend/vite.config.ts`
- Test: `property_rental/rentals/tests/test_static_build.py`

**Interfaces:**
- Produces: image `property-rental:life-os` exposing internal port 8000 by default.
- Produces: Docker health check against `/health/live` with correct `${PORT:-8000}` expansion.
- Consumes: build settings and Gunicorn config from Tasks 1 and 5.

- [ ] **Step 1: Write failing static/build contract tests and audit script**

Test build settings reject missing/invalid Vite manifest and accept the actual manifest entry. Define `container_smoke.py` assertions for UID, executable absence (`node`, `npm`, `uv`, `gcc`, `cc`), forbidden filename patterns (`*.sqlite3`, `*.map`, `.env*`, Playwright/test fixture paths), package caches, PostgreSQL production engine, liveness/static/SPA responses, and graceful termination.

- [ ] **Step 2: Verify static tests fail before Docker assets exist**

Run: `uv run pytest property_rental/rentals/tests/test_static_build.py -q`

Expected: tests fail on absent build settings validation or manifest contract.

- [ ] **Step 3: Implement Vite and Docker build**

Disable production source maps explicitly. In the Node 20 stage copy only package manifests first, use a BuildKit npm cache mount, run `npm ci`, copy required frontend source, and run `npm run build`. In the Python 3.11 slim builder install uv temporarily, use a cache mount, and run `uv sync --frozen --no-dev --no-editable` into `/opt/venv`. In the matching slim runtime copy `/opt/venv`, Django source, built frontend output, run offline `collectstatic` in a build stage, copy collected assets, create a fixed non-root UID/GID, and invoke Gunicorn directly without a shell migration wrapper.

- [ ] **Step 4: Implement strict build context and non-secret example**

Allow only files required by the two builders and runtime. Document environment names using obvious non-working placeholders such as `<provision-in-life-os>` only in the example file; ensure `.env.production.example` itself is excluded from the final image.

- [ ] **Step 5: Build and audit the image**

Run:

```powershell
docker build --pull --tag property-rental:life-os .
docker image inspect property-rental:life-os
docker history --no-trunc property-rental:life-os
python scripts/container_smoke.py --image property-rental:life-os
```

Expected: build exits 0; audit proves all runtime-content, non-root, health, static, SPA, PostgreSQL-settings, and SIGTERM contracts.

- [ ] **Step 6: Commit the production image**

```powershell
git add Dockerfile .dockerignore .env.production.example scripts/container_smoke.py frontend/vite.config.ts property_rental/rentals/tests/test_static_build.py
git commit -m "feat: add minimal production container"
```

---

### Task 9: Add PostgreSQL and Container CI Gates

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `scripts/ci_postgres.ps1`
- Create: `scripts/ci_container.ps1`

**Interfaces:**
- Produces: PostgreSQL service-backed backend job using `property_rental.settings.test_postgres`.
- Produces: image build/audit job dependent on frontend test, lint, build, and backend jobs.

- [ ] **Step 1: Validate the current workflow lacks required gates**

Run: inspect `.github/workflows/ci.yml` and record that backend tests currently use development SQLite and no image audit exists. Use a YAML parser if available to ensure later edits remain syntactically valid.

- [ ] **Step 2: Add PostgreSQL service and migration/import coverage**

Configure a health-checked PostgreSQL service with CI-only credentials, pass a PostgreSQL `DATABASE_URL`, run `migrate --noinput`, `pytest --cov=rentals`, importer PostgreSQL markers, and `check --deploy` with non-production CI secrets. Keep the supported Python matrix unless a dependency proves incompatible; database-sensitive coverage must include Python 3.11.

- [ ] **Step 3: Add image build and runtime-audit job**

Require existing frontend test/lint/build and backend jobs first. Build from checkout, run `scripts/container_smoke.py`, export Docker image inspection/history, and calculate compressed OCI archive and uncompressed image sizes as artifacts/log output. Do not run tests inside `docker build`.

- [ ] **Step 4: Verify workflow syntax and local script behavior**

Run:

```powershell
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"
docker build --tag property-rental:life-os .
python scripts/container_smoke.py --image property-rental:life-os
```

Expected: YAML parses, image builds, audit passes.

- [ ] **Step 5: Commit CI gates**

```powershell
git add .github/workflows/ci.yml scripts/ci_postgres.ps1 scripts/ci_container.ps1
git commit -m "ci: verify PostgreSQL and production container"
```

---

### Task 10: Write the Life OS, Migration, Backup, and Image Handoff

**Files:**
- Modify: `README.md`
- Create: `docs/deployment/life-os.md`
- Create: `docs/deployment/sqlite-migration.md`
- Create: `docs/deployment/backup-restore.md`
- Create: `docs/deployment/image-report.md`

**Interfaces:**
- Produces: complete application-side contract for the later Life OS integration agent.
- Consumes: verified commands, environment names, routes, network names-as-roles, and measured image evidence from prior tasks.

- [ ] **Step 1: Write the deployment contract from verified implementation**

Document image build/run commands, explicit migration job, no implicit migration, every environment variable with required/optional and secret classification, `rent.linik.ru`, internal port, liveness/readiness, proxy-header overwrite requirement, no host port, edge/proxy versus application-data networks, dedicated least-privilege database, Authentik callback/logout/PKCE/group requirements, missing admin-group provisioning, scheduled FX command/timezone, and production-disabled local auth/effective-date behavior.

- [ ] **Step 2: Write the SQLite migration runbook**

Document source backup, read-only mount, preflight/dry-run, empty-business-table definition, destination migration, import, reconciliation review, unusable imported passwords, explicit issuer/subject linking, smoke checks, fail-closed cases, and rollback through Life OS database recreation. State that the importer is temporary tooling and not routine startup.

- [ ] **Step 3: Write backup and restore notes**

Identify the dedicated rental PostgreSQL database as the sole persistent data at launch and explicitly state that there are no upload/media fields. Document logical/shared-server restore isolation, migration-state validation, sequence checks, ownership reconciliation, OIDC relinking considerations, and health/application smoke tests. State that future uploads require a new persistence contract.

- [ ] **Step 4: Measure and record image size**

Run:

```powershell
docker image inspect property-rental:life-os --format '{{.Size}}'
docker history property-rental:life-os --format '{{.Size}}`t{{.CreatedBy}}'
docker save property-rental:life-os -o property-rental-life-os.tar
gzip -9 -k property-rental-life-os.tar
```

Record exact uncompressed Docker size, compressed archive size, measurement date/platform, largest layers, and largest installed Python packages. Delete the local measurement archives after recording values; do not commit them.

- [ ] **Step 5: Check documentation against the approved design**

Run:

```powershell
rg -n "DATABASE_URL|migrate --noinput|import_sqlite|refresh_fx|lifeos:app:rent:viewer|lifeos:app:rent:admin|health/live|health/ready|edge/proxy|application-data|Restic|image size" README.md docs/deployment
git diff --check
```

Expected: every contract term is present and the diff has no whitespace errors.

- [ ] **Step 6: Commit handoff documentation**

```powershell
git add README.md docs/deployment
git commit -m "docs: add Life OS deployment contract"
```

---

### Task 11: Full Acceptance Verification

**Files:**
- Modify only files needed to correct failures proven during verification.

**Interfaces:**
- Produces: fresh evidence for every acceptance criterion and final handoff.

- [ ] **Step 1: Run complete backend tests on PostgreSQL**

Run the CI PostgreSQL script, including migration from an empty database and the full pytest suite with coverage.

Expected: zero failures and no unexpected warnings.

- [ ] **Step 2: Run complete frontend verification**

Run:

```powershell
Push-Location frontend
npm ci
npm test
npm run lint
npm run build
$env:PW_CHANNEL='chrome'
npm run test:e2e -- --workers=1
Pop-Location
```

Expected: unit tests, lint, production build, and Playwright scenarios pass.

- [ ] **Step 3: Run Django schema and security verification**

Run `makemigrations --check --dry-run`, empty-PostgreSQL `migrate --noinput`, production `check --deploy`, importer reconciliation, and OIDC/authorization focused tests with the documented environment contract.

Expected: no model drift, migrations complete, security checks pass, import reconciles, and auth tests pass.

- [ ] **Step 4: Rebuild from a clean tracked context and audit runtime**

Use `git archive HEAD` or a clean temporary checkout as Docker build context so ignored/local files cannot influence the result. Build the final image, run the full container audit, verify liveness/readiness behavior, serve one hashed static asset and a React route, inspect non-root UID, and send SIGTERM while checking graceful exit.

Expected: every audit assertion passes and the runtime contains none of the forbidden content.

- [ ] **Step 5: Re-measure final image and update only measured evidence**

Repeat the image inspect/history/save/compress commands after the final rebuild. If values changed, update `docs/deployment/image-report.md` and rerun its contract scan.

- [ ] **Step 6: Review the acceptance checklist line by line**

Compare fresh command output with all 14 acceptance criteria in `docs/superpowers/specs/2026-07-31-life-os-production-preparation-design.md`. Report any unmet criterion honestly; do not mark preparation complete while a required PostgreSQL, Docker, OIDC, test, or measurement check is unverified.

- [ ] **Step 7: Commit verification-only corrections or evidence**

If verification changed tracked documentation or code, stage only those files, rerun the affected full checks, and commit with `chore: finalize production verification`. If no tracked file changed, do not create an empty commit.
