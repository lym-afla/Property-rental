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

Production must leave `LOCAL_PASSWORD_AUTH_ENABLED` unset or false. If it is set
true under production settings, Django refuses startup.

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

The command accepts `--date YYYY-MM-DD` and repeatable `--pair FROM/TO`
arguments. Without `--date`, it uses the configured business timezone's current
local date.

Ordinary web requests and financial mutations do not invoke external FX
providers. A transaction commit is independent of Yahoo Finance availability.
The UI reports cached FX data and tells the operator that scheduled refresh is
required when rates are absent.

FX persistence is deterministic:

- the canonical rate identity is `(date, source, from_currency, to_currency)`;
- upserts do not create duplicate rates;
- failed refreshes retain existing valid rates;
- refresh reports distinguish cached, newly fetched, unavailable, and invalid
  rates;
- outbound calls have bounded timeouts, and no retries are performed from web
  requests.

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

