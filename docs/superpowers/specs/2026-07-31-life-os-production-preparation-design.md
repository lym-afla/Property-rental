# Life OS Production Preparation Design

**Date:** 2026-07-31

**Status:** Approved

## Objective

Prepare Property Rental as the first production application within Life OS without deploying it or modifying the Life OS infrastructure repository. The repository will build one reproducible, non-root production image that serves the Django API and compiled React SPA, connects to a dedicated database on the shared Life OS PostgreSQL server, authenticates through Authentik OIDC, and exposes a precise deployment contract for the later Life OS integration task.

Existing rental behavior, ownership relationships, analytics, and tests must remain intact. SQLite may remain an explicit development or isolated-test option, but production must fail rather than silently select SQLite.

## System Boundary

Production request and data flow:

```text
Internet
  -> Traefik :443
    -> rental container :${PORT}
      -> Gunicorn / Django
        |- /api/v1/*       DRF using the Django session
        |- /oidc/*         Authentik authorization-code flow with PKCE
        |- /health/live    process-only liveness
        |- /health/ready   PostgreSQL readiness
        |- /static/*       WhiteNoise
        `- /*              compiled React SPA
      -> shared PostgreSQL / dedicated rental database

One-shot or scheduled jobs using the same application image:
  manage.py migrate --noinput
  manage.py import_sqlite --source /migration/db.sqlite3
  manage.py refresh_fx
```

The Life OS deployment owns database and role creation, secrets, Docker network attachment, Traefik routing, Authentik registration and group provisioning, scheduling, backup execution, catalogue activation, and release orchestration. This repository supplies the image and documented contract only. It must not create PostgreSQL, Traefik, Authentik, or a separate frontend server in production.

## Container Architecture

Use one multi-stage Dockerfile with compatible Debian/Python bases for all Python stages:

1. The Node builder runs only `npm ci` and `npm run build`. Vite source maps are disabled. Frontend tests and lint run in CI before the image build.
2. The Python/uv builder installs the locked Python 3.11 production dependency set into a virtual environment at the same absolute path used by the runtime image. This repository's `dev` dependency group is excluded with `uv sync --frozen --no-dev --no-editable`.
3. The minimal Python 3.11 slim runtime contains the application, the production virtual environment, compiled SPA assets, collected Django static assets, and Gunicorn. It runs as a dedicated non-root user.

`collectstatic` runs during image construction with a dedicated build settings module. That settings path requires no database or OIDC connection, does not use or embed placeholder secrets, collects deterministic static files only, and fails when the expected Vite manifest or entry asset is absent. Runtime startup performs no npm operation, frontend build, dependency installation, migration, or static collection.

Gunicorn is the sole application process. It binds to an environment-configurable `PORT`, writes access and error logs to stdout/stderr, uses settings appropriate for graceful SIGTERM handling, and retains no essential state in the writable container filesystem.

The strict `.dockerignore` excludes Git data, local databases, virtual environments, caches, environment files, development documentation, test code and fixtures, Playwright data and browser artifacts, frontend source maps, and other build-irrelevant assets. Required source files are copied by explicit build-stage boundaries.

## Runtime Configuration

Production configuration is environment-driven and validated before Gunicorn starts. Missing or invalid required values cause a clear startup failure. Production requires at least:

- `DATABASE_URL`, whose scheme must select PostgreSQL;
- `DJANGO_SECRET_KEY`;
- `DJANGO_ALLOWED_HOSTS`, containing `rent.linik.ru`;
- `DJANGO_CSRF_TRUSTED_ORIGINS`, containing `https://rent.linik.ru`;
- `PORT`, with a documented internal default;
- `BUSINESS_TIME_ZONE`;
- OIDC issuer, client ID, client secret, callback URL, logout behavior, required viewer group, admin group, and authorization-renewal interval.

A committed non-secret example documents names and safe example values but contains no credentials. Neither source, Dockerfile, Compose definitions, image layers, nor generated static files contain secrets. Production settings cannot fall back to SQLite if `DATABASE_URL` is absent or malformed.

No CORS package or CORS permission headers are introduced because the SPA and API are same-origin. A cross-origin policy may be added only when a real client requires it.

## PostgreSQL and Schema Authority

The rental application uses one dedicated database and credentials on the shared Life OS application PostgreSQL server. Those credentials must have no access to other application databases. Production does not create or bundle another PostgreSQL server.

Standard Django migrations are the sole schema authority. Life OS runs `python property_rental/manage.py migrate --noinput` as an explicit one-shot deployment job before releasing the web container. The normal web entrypoint never applies migrations.

CI provides PostgreSQL for database-sensitive backend behavior and verifies that all migrations apply to an empty database. Explicit development settings may continue using SQLite. Test settings must make the selected backend visible and must not accidentally turn a production-settings test into SQLite.

## Temporary SQLite Import

The repository includes a tested, temporary `import_sqlite` management command for the actual one-time data move. It is migration tooling, not part of normal startup or the permanent runtime contract. It may execute from the application image for dependency consistency, but the entrypoint, health checks, and routine deployment never invoke it.

The importer accepts a SQLite file mounted only for the migration job and writes only to PostgreSQL. Its destination precondition is a migrated database whose rental business tables are empty. Django system tables may already contain migration, content-type, and permission rows.

The command:

- validates source schema and supported migration state before writes;
- uses an atomic transaction;
- preserves application primary and foreign keys;
- imports in dependency order;
- resets PostgreSQL sequences after explicit primary-key insertion;
- validates per-table counts, foreign-key relationships, and expected ownership chains;
- produces a machine- and human-readable reconciliation report;
- is idempotent for an already completed, exactly matching import;
- fails closed on partial, conflicting, ambiguous, or non-empty application data.

Imported `User` rows remain local ownership records and retain their primary keys because landlords, properties, tenants, and transactions depend on them. Imported passwords are made unusable; no usable production password hash survives the import.

OIDC identity linkage happens separately after import using verified issuer and subject values. It is never inferred from email or username. If an imported user cannot be associated unambiguously with the intended Life OS identity, linkage fails closed and that user cannot gain production access until an operator resolves it.

The migration runbook includes source backup, dry-run/preflight, destination migration, import, reconciliation review, OIDC linkage, smoke testing, and rollback by discarding/recreating the dedicated destination database through Life OS.

## OIDC Identity and Authorization

Use a pinned, Django-compatible release of `mozilla-django-oidc`, locked in `uv.lock`. The authorization-code flow explicitly enables:

```python
OIDC_USE_PKCE = True
OIDC_PKCE_CODE_CHALLENGE_METHOD = "S256"
```

The library's base `OIDCAuthenticationBackend` remains responsible for protocol mechanics and cryptographic validation, including signature, audience, nonce, and PKCE exchange. A narrow custom subclass handles only local identity binding, mutable profile synchronization, and application claims. It must not reimplement token cryptography.

Add an `OIDCIdentity` model with:

- a one-to-one relation to the existing local `User`, allowing exactly one OIDC identity per user;
- immutable `issuer` and `subject` values;
- a database uniqueness constraint on `(issuer, subject)`.

Email and username are mutable profile attributes and never durable identity keys. Existing `User`, `Landlord`, `Property`, `Tenant`, and `Transaction` relationships remain unchanged.

The required application authorization claim is `lifeos:app:rent:viewer`. Group claims grant authorization only; they never establish or merge identity. Login fails unless the required viewer group is present.

The Django session stores `last_authorized_at`. It is set only after an initial or renewed OIDC callback succeeds and revalidates the viewer group. An environment-configurable authorization-renewal interval has a five-minute production default.

`mozilla-django_oidc.middleware.SessionRefresh` performs silent OIDC renewal for eligible GET requests. Application authorization middleware independently enforces the same maximum authorization age on every protected request:

- For eligible GET/XHR requests, the library may return `403` with `refresh_url`; the React API client recognizes that response and performs a top-level browser navigation to the refresh URL.
- For expired POST, PATCH, PUT, or DELETE requests, middleware rejects the request before view execution with a defined authentication-refresh response. The React client starts a top-level refresh but never replays the mutation automatically. The user must deliberately retry it.
- If renewed claims lack `lifeos:app:rent:viewer`, the local session is cleared and access is denied.

The requested local URL survives the OIDC flow through a validated `next` parameter restricted to same-host/local paths. Production password login, self-registration, and password-change endpoints and UI are disabled. Development may retain them only behind an explicit non-production setting.

Django administration, if retained, uses OIDC and additionally requires the expected claim `lifeos:app:rent:admin`; local `is_staff` alone is insufficient in production. This group does not yet exist in the Life OS catalogue, so the Life OS deployment task must create and provision it. Logout clears the local session and follows environment-driven Authentik end-session and return behavior.

## Proxy and Django Security

The container is reachable only through controlled Life OS Docker networks. Django configures `SECURE_PROXY_SSL_HEADER` for Traefik's overwritten HTTPS indication. Traefik must overwrite security-relevant proxy headers. The application does not consume forwarded identity or role headers and does not broadly trust arbitrary forwarded client-address headers.

Production enforces:

- `DEBUG = False`;
- exact allowed hosts and trusted HTTPS CSRF origins;
- secure, HTTP-only session cookies and secure CSRF cookies;
- appropriate SameSite behavior for the OIDC redirect flow;
- HTTPS redirect and HSTS appropriate for proxy termination;
- content-type sniffing, referrer, clickjacking, and related Django security headers;
- generic user-facing error responses and stdout/stderr server logging.

The two required networks are separate contracts:

- edge/proxy network: Traefik can reach the rental web container;
- application-data network: the rental container can reach the shared PostgreSQL container.

The rental container does not join unrelated application networks and publishes no host port.

## Health and Lifecycle

`GET /health/live` proves only that Django can answer. It has no database, Authentik, or external-network dependency.

`GET /health/ready` performs a minimal query through Django's configured PostgreSQL connection. It reports unavailable on database failure and does not contact Authentik or the FX provider.

The Docker `HEALTHCHECK` targets liveness using Python's standard library. It uses either the documented fixed internal default or shell-form expansion that correctly resolves `PORT`; it does not rely on exec-form environment expansion. Life OS separately uses readiness to gate traffic or release progression.

## FX Acquisition

Ordinary web requests and financial mutations never contact the external FX provider. Saving a transaction commits independently of FX availability. At launch, production FX acquisition occurs only through the scheduled `refresh_fx` management command. The UI may show FX freshness, unavailable/cached state, and that scheduled refresh is required, but it does not claim to enqueue background work.

No Redis, Celery, queue, or additional service is introduced. A future durable job mechanism may support user-requested refresh only if operational evidence justifies it.

FX persistence has a database-level unique identity over effective date, source currency, and target currency using one documented canonical pair representation. Refresh behavior:

- uses explicit connect/read bounds and bounded retries only for safe reads;
- normalizes rate pairs consistently;
- uses idempotent upserts and never creates duplicate rate identities;
- uses stored valid rates as the durable cache;
- never overwrites or deletes an existing valid rate because a refresh failed;
- reports cached, newly fetched, unavailable, and invalid rates separately;
- exits nonzero when required requested rates remain unavailable or invalid;
- uses `BUSINESS_TIME_ZONE` for date selection, scheduling guidance, and reporting.

## Effective Date

The README identifies the per-user effective-date override as developer functionality. Production removes it from profile/API mutation and does not let a persisted user override redefine the application's current business date. Production calculations use the current date in `BUSINESS_TIME_ZONE` unless a specific analytics endpoint accepts and validates an explicit bounded historical range. Development-only behavior, if retained for tests, must be clearly isolated from production.

## Static SPA Delivery

Vite outputs hashed production assets and a manifest with source maps disabled. The build settings validate that the manifest and expected `src/main.tsx` entry exist before static collection. WhiteNoise collects and serves compressed, manifest-versioned Django and SPA assets. Django's SPA fallback serves the compiled shell for client-side routes while API, OIDC, admin, health, and static routes remain explicit and take precedence.

Runtime performs no frontend compilation or `collectstatic` operation.

## Persistent Data and Backup Contract

No current model contains uploaded-file or image fields, so the launch design has no application media volume. The dedicated rental PostgreSQL database is the only essential persistent application state. Life OS must include that database in its encrypted off-VPS Restic-backed PostgreSQL backup workflow and document point-in-time or logical restore steps appropriate to the shared server.

Restore validation includes provisioning an empty dedicated database and role, restoring rental data without affecting other application databases, applying/validating Django migration state, resetting sequences when needed, verifying reconciliation counts and ownership chains, linking Authentik identities, and running readiness and application smoke checks.

If uploads are introduced later, production use is blocked until an explicit persistent media/object-storage contract and backup/restore procedure are added.

## CI and Verification

CI preserves all existing backend, analytics, frontend unit, lint, build, and Playwright coverage. It adds:

- PostgreSQL-backed backend/database-sensitive tests;
- migration application against a new empty PostgreSQL database;
- SQLite importer preflight, success, idempotency, sequence, reconciliation, password-disablement, and failure-mode tests;
- OIDC identity uniqueness, claim authorization, renewal-age, XHR refresh, mutation rejection/no-replay, logout, and admin-role tests;
- production settings and `check --deploy` validation;
- frontend production build before Docker construction;
- reproducible Docker build from a clean checkout;
- container liveness, readiness, static asset, SPA fallback, and SIGTERM smoke tests;
- runtime-content assertions proving:
  - no Node.js, npm, uv, compiler, or package-manager cache;
  - no SQLite database;
  - no source maps;
  - no test code, fixtures, Playwright artifacts, or browser binaries;
  - a non-root process UID;
  - no committed environment file or secret;
  - production settings select PostgreSQL only.

Image reporting records the measured compressed registry-equivalent size, uncompressed Docker size, and the largest layers and dependency contributors. Required analytics functionality remains even when its packages dominate image size.

## Deployment Contract for Life OS

The repository's deployment notes provide the integration agent with:

- image build command, immutable tag/digest expectations, internal port, health paths, and explicit migration command;
- every required and optional environment variable, including secret/non-secret classification;
- dedicated rental database and least-privilege role requirements without embedding their values;
- edge/proxy and application-data network requirements;
- Traefik hostname `rent.linik.ru`, TLS/proxy-header expectations, and no-host-port rule;
- Authentik OIDC callback/logout URIs, claims, PKCE requirements, viewer group, and not-yet-provisioned admin group;
- `refresh_fx` scheduling and business-timezone requirements;
- SQLite import and identity-linking runbook when existing data is migrated;
- persistent data, backup, restore, and verification requirements;
- measured image sizes and runtime-content audit results.

No VPS deployment or Life OS infrastructure change is performed from this repository.

## Acceptance Criteria

Preparation is complete only when fresh verification proves:

1. A clean checkout reproducibly builds the production image.
2. Frontend tests and lint run in CI outside the Docker build; the Node stage itself runs only `npm ci` and `npm run build`.
3. The final image contains the Django application, locked production dependencies, compiled SPA, collected static assets, and Gunicorn, but none of the forbidden runtime content.
4. The process runs as non-root, listens on one internal configurable port, logs to stdout/stderr, stops cleanly, and keeps no essential writable-container state.
5. Production requires PostgreSQL through `DATABASE_URL` and cannot silently select SQLite.
6. Migrations succeed against an empty PostgreSQL database as an explicit job.
7. The temporary importer safely reconciles the intended SQLite data and disables imported passwords.
8. OIDC uses PKCE S256, durable `(issuer, subject)` identity, viewer authorization, bounded renewal age on every protected request, and no automatic mutation replay.
9. The compiled SPA, API, static files, liveness, and PostgreSQL readiness are served correctly by the one production container.
10. Financial writes perform no external FX call; scheduled refresh is bounded, deterministic, idempotent, and preserves valid cached data on failure.
11. Existing backend, analytics, frontend, and browser tests pass, with PostgreSQL coverage for database-sensitive behavior.
12. No secrets, local SQLite database, uploaded media, or other persistent runtime state are embedded in the image.
13. Compressed and uncompressed image sizes and largest contributors are measured and documented.
14. Life OS integration, database provisioning, routing, Authentik configuration, scheduling, backups, and deployment remain explicitly out of scope for repository execution.
