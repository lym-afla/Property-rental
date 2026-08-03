# Life OS deployment contract

This repository now provides an application-side contract for running the
Property Rental app as the first production Life OS application at
`https://rent.linik.ru`. Deployment, database/user provisioning, Traefik
routing, Authentik registration, backups, and catalogue activation remain
outside this repository.

## Runtime shape

Production uses one application container:

```text
Traefik -> Django/Gunicorn -> API + compiled React SPA + WhiteNoise static files
                         -> shared Life OS PostgreSQL application server
```

Do not add a second PostgreSQL container, Traefik instance, Authentik instance,
frontend dev server, or Nginx container for production.

The image is built by the root `Dockerfile`:

- Node builder: `npm ci`, then `npm run build`.
- Python/uv builder: installs the locked Python 3.11 production dependency set
  into `/opt/venv` with `uv sync --frozen --no-dev --no-editable`.
- Static builder: runs `collectstatic` with `property_rental.settings.build`.
  This settings module requires no database connection, no OIDC connection, and
  fails if the expected Vite manifest is absent.
- Runtime: Python 3.11 slim Debian, non-root UID/GID `10001`, Gunicorn only,
  compiled frontend assets and collected Django static files served by
  WhiteNoise.

Runtime startup performs no frontend build, no `collectstatic`, and no database
migration.

Production images are published to GHCR only with immutable full-commit SHA
tags:

```text
ghcr.io/lym-afla/property-rental:sha-<full-commit-sha>
```

Life OS deployments must pin this immutable SHA tag or a registry digest. Do
not deploy `latest`; the repository workflow does not publish a `latest` tag.

## Networks

The Life OS compose stack should attach the rental container only to:

- edge/proxy network: Traefik -> rental web container.
- application-data network: rental web container -> shared application
  PostgreSQL container.

The rental container must not publish a host port and must not join unrelated
application networks. Traefik is the only public HTTP entry point.

## Required runtime environment

Use `.env.production.example` as the non-secret shape only. Provision real
secret values through the Life OS secret/environment mechanism, not in the
image, source code, committed env files, or production compose definitions.

Required:

| Variable | Secret | Production value/notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Dedicated database and dedicated credentials inside the shared Life OS application PostgreSQL server. Must be `postgresql://` or `postgres://`; production settings reject SQLite. |
| `DJANGO_SECRET_KEY` | yes | Unique high-entropy Django secret key. |
| `DJANGO_ALLOWED_HOSTS` | no | `rent.linik.ru` initially. Comma-separated. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | no | `https://rent.linik.ru`. Comma-separated. |
| `BUSINESS_TIME_ZONE` | no | Explicit business timezone, currently `Europe/Moscow`. |
| `OIDC_ISSUER` | no | Authentik issuer URL for the rental application. |
| `OIDC_CLIENT_ID` | no | Authentik OIDC client id. |
| `OIDC_CLIENT_SECRET` | yes | Authentik OIDC client secret. |
| `OIDC_CALLBACK_URL` | no | `https://rent.linik.ru/oidc/callback/` unless Life OS registers a different callback path. |
| `OIDC_LOGOUT_URL` | no | Authentik end-session/logout URL for the app. |

Optional:

| Variable | Default | Notes |
| --- | --- | --- |
| `PORT` | `8000` | Internal listen port. The Docker health check expands this through shell form. |
| `GUNICORN_WORKERS` | `2` | Gunicorn worker count. |
| `OIDC_AUTHORIZATION_MAX_AGE` | `300` | Maximum age, in seconds, of locally authorized OIDC group claims. Production default is five minutes. |
| `LIFE_OS_PROFILE_URL` | unset | Optional central Life OS profile-management URL. When set, production accepts only HTTPS URLs on the exact origin `https://linik.ru`, for example `https://linik.ru/profile`. Do not set this until that central page exists. |

Production must leave `LOCAL_PASSWORD_AUTH_ENABLED` unset or false. If it is set
true under production settings, Django refuses startup.

Production also sets `OIDC_CREATE_USER=False`. Unknown Authentik identities do
not auto-create local users; imported/local ownership records must be linked
deliberately with verified `(issuer, subject)` values.

## Database contract

Life OS must create:

- one dedicated rental database inside the shared custom-application PostgreSQL
  server;
- one dedicated rental database role/password with access only to that rental
  database/schema;
- network connectivity from the rental container on the application-data
  network to the shared PostgreSQL container.

This repository does not create a PostgreSQL server in production.

Django migrations are the schema authority:

```bash
python manage.py migrate --noinput
```

Run migrations as an explicit one-shot deployment job using the same image and
runtime environment as the web container. Do not run migrations implicitly in
the web container entrypoint.

An "empty rental database" for first install means application/business tables
are empty after Django migrations. Django system tables such as migrations,
content types, permissions, and sessions may already contain rows.

## Authentication and authorization

Production authentication uses Authentik OpenID Connect through
`mozilla-django-oidc==5.0.2`. The base OIDC backend performs protocol
validation, including token signature, audience, nonce, and the PKCE exchange.
The custom backend handles only application-specific issuer/subject binding and
group-claim authorization.

The app explicitly requires PKCE:

```text
OIDC_USE_PKCE=True
OIDC_PKCE_CODE_CHALLENGE_METHOD=S256
```

Durable identity is `(issuer, subject)`, stored in `rentals_oidcidentity` with a
database-level unique constraint. Each local user can have one OIDC identity.
Email and username are mutable profile attributes and are never durable identity
keys.

Authentik/Life OS is the source of truth for username, first name, last name,
email, passwords, passkeys, MFA, and application roles. After the base OIDC
backend validates the callback/userinfo flow and the required viewer group is
present, Rent syncs those mutable profile claims onto the already-linked local
`User` row. Missing, blank, or malformed optional profile claims do not erase
existing local values. Unknown users are not created or linked from matching
email or username.

The local `User` row remains a Rent ownership/preferences projection for
foreign keys such as landlords, properties, tenants, transactions, and report
preferences. Ordinary production API requests cannot edit `username`,
`first_name`, `last_name`, or `email`; those fields are shown read-only in the
SPA's Life OS identity section.

The SPA can optionally show a "Manage Life OS profile" link. The current
production deployment leaves `LIFE_OS_PROFILE_URL` unset, so no link is shown.
When Life OS later deploys the central page, set:

```text
LIFE_OS_PROFILE_URL=https://linik.ru/profile
```

Do not point Rent at Authentik's generic user dashboard or invent an internal
Authentik flow URL. Future direct Authentik security-flow links must be
separately configured and validated for that specific purpose.

Group claims are authorization, not identity. The app initially requires:

- `lifeos:app:rent:viewer` for application access.
- `lifeos:app:rent:admin` for Django admin access if the admin remains enabled.
  This role does not yet exist in the Life OS catalogue; Life OS must add and
  provision it before admin access can work.

On login and renewed OIDC callback, the app validates that
`lifeos:app:rent:viewer` is present. Loss of the viewer group clears the local
session and denies access.

The session stores a `last_authorized_at` timestamp. Application middleware
enforces `OIDC_AUTHORIZATION_MAX_AGE` on every protected request. GET/XHR
requests may use mozilla-django-oidc's `SessionRefresh` behavior, which returns
a `403` plus `refresh_url`; the React API client performs a top-level browser
redirect to that URL. Expired `POST`, `PATCH`, and `DELETE` requests are
rejected before reaching the view with a defined refresh-required response, and
the client never automatically replays a failed financial mutation after
reauthentication.

Do not trust identity, role, or group headers from the public internet. This
application consumes OIDC claims from Authentik, not forwarded identity headers.

In production, Django admin also treats Life OS identity fields and Django
password hashes as read-only. Local `is_staff` and `is_superuser` remain
operational flags, but they do not grant admin access without the OIDC
`lifeos:app:rent:admin` group.

## HTTPS/proxy/security expectations

The container is reachable only through controlled Life OS Docker networks.
Django sets:

- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- secure session and CSRF cookies
- HSTS
- `DEBUG = False`
- strict `ALLOWED_HOSTS`
- strict `CSRF_TRUSTED_ORIGINS`

Traefik must overwrite security-relevant proxy headers before forwarding. The
application does not broadly trust arbitrary forwarded client-address headers.

The SPA and API are same-origin at `https://rent.linik.ru`, so no CORS package
or CORS permission headers are configured for production.

## Health checks

- `GET /health/live` checks only that the Django process can answer. It has no
  database or external-network dependency.
- `GET /health/ready` confirms Django can query PostgreSQL with `SELECT 1`.

Both endpoints are anonymous and precede the SPA catchall route.

The Docker health check uses `/health/live`; readiness should be checked by
Life OS/Traefik deployment logic before routing traffic.

## FX acquisition

At launch, production FX acquisition is performed only by:

```bash
python manage.py refresh_fx
```

With no arguments, the command performs an idempotent full gap scan through the
configured business timezone's current local date. It derives required effective
dates and currency pairs from dated monetary business records: transactions,
property capital-structure rows, lease-rent history, and tenant monthly rent due
dates. Existing valid rates are kept; only missing or non-positive
`(date, from_currency, to_currency)` rows are fetched.

The command also accepts `--scan-gaps --through YYYY-MM-DD` for an explicit gap
scan cutoff, and `--date YYYY-MM-DD` with repeatable `--pair FROM/TO` for
manual single-date repair. The manual mode is not the normal production
schedule.

Ordinary web requests and financial mutations do not invoke external FX
providers. A transaction commit is independent of Yahoo Finance and CBR
availability. The UI reports cached FX data and tells the operator that
scheduled refresh is required when rates are absent.

FX persistence is deterministic:

- the canonical rate identity is `(date, from_currency, to_currency)`, where
  `rate` is the direct multiplier from the canonical `from_currency` to
  `to_currency`;
- upserts do not create duplicate rates;
- failed refreshes retain existing valid rates;
- refresh reports distinguish cached, newly fetched, unavailable, and invalid
  rates;
- RUB-related canonical pairs are fetched from the Central Bank of Russia over
  HTTPS; non-RUB pairs are fetched from Yahoo Finance;
- CBR publishes RUB per foreign unit, so the provider stores direct canonical
  rates without ambiguity: `EUR/RUB` stores RUB per EUR, while canonical
  `RUB/USD` stores USD per RUB by inverting CBR's RUB-per-USD quote;
- CBR responses are cached per provider date within a refresh run, so multiple
  RUB-related pairs for the same date reuse one SOAP response;
- Yahoo and CBR both walk back over recent prior dates when the requested
  effective date is a market holiday or weekend, while storing the rate under
  the rental effective date required by the business record;
- outbound calls have bounded timeouts, and no retries are performed from web
  requests. The scheduled adapters retry transient CBR rate-limit/server/network
  failures with bounded backoff.

The runtime image sets `XDG_CACHE_HOME=/tmp/.cache`; in Life OS `/tmp` is a
tmpfs mount, so provider caches are writable, ephemeral, and not embedded in the
image or backup contract.

Schedule `refresh_fx` from Life OS using the same image and environment as the
web container. No Redis, Celery, or queue service is required for launch.

## Static assets and persistent data

The production image contains the compiled React SPA and collected Django
static assets. WhiteNoise serves both from the Django/Gunicorn process.

No uploaded media/document model is present at launch, so the rental application
has no persistent media volume requirement today. If future uploads are added,
Life OS must mount that media path outside the writable container filesystem and
include it in the backup contract.

The container filesystem holds no essential runtime state.

## Smoke/runtime assertions

CI and `scripts/container_smoke.py` assert that the final runtime:

- runs as non-root;
- selects PostgreSQL under production settings;
- contains no Node.js, npm, uv, gcc, or cc;
- contains no package-manager cache directories;
- contains no local SQLite databases;
- contains no frontend source maps;
- contains no app tests, Playwright/e2e directories, or test fixtures;
- contains no committed `.env*` file or secret-shaped environment file;
- serves `/health/live`;
- serves the compiled SPA and frontend assets.
