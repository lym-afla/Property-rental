# Backup and restore notes

Life OS owns encrypted off-VPS Restic backups. This repository identifies what
must be included for the rental app; it does not configure or run the VPS
backup system.

## Persistent data at launch

Required:

- the dedicated rental PostgreSQL database inside the shared Life OS
  application PostgreSQL server.

Not required at launch:

- a media/uploads volume. The current application has no uploaded document or
  media persistence contract.

The web container filesystem should be treated as disposable. Compiled static
assets are rebuilt from source into the image and are not backup data.

## Suggested backup contents

Back up the dedicated rental database separately from Authentik's exclusive
database and separately from other Life OS application databases. The rental
database credentials should not be able to read those other databases.

Capture enough metadata to restore:

- database name;
- database owner/role name, but not plaintext secrets in the backup manifest;
- image tag or commit deployed;
- migration state from `django_migrations`;
- any future media volume path if uploads are later introduced.

## Restore outline

1. Provision a fresh dedicated rental PostgreSQL database and least-privilege
   role in the shared application PostgreSQL server.
2. Restore the database dump into that database.
3. Start a one-shot migration job from the target application image:

   ```bash
   python manage.py migrate --noinput
   ```

4. Confirm readiness:

   ```bash
   python manage.py check --deploy
   curl -fsS https://rent.linik.ru/health/ready
   ```

5. Confirm OIDC users still have expected `rentals_oidcidentity` rows. Do not
   rebuild identity mappings from email.
6. Confirm the restored schema contains the Rent OIDC session registry and
   logout replay-protection tables (`rentals_oidcsession` and
   `rentals_oidclogoutreplay`). Verify schema presence and migrations only;
   never print session keys, provider session identifiers, subjects, tokens,
   cookies, headers, response bodies, or table contents into restore evidence.
7. If FX rates are stale or intentionally absent for restored business-record
   dates, run the scheduled full gap scan once:

   ```bash
   python manage.py refresh_fx
   ```

   The command derives required dates and currency pairs from restored rental
   records, fetches only missing/non-positive FX rows, and prints compact
   cached/fetched/unavailable/invalid counts by default. Use `--json` or
   `--verbose` only when a full per-rate reconciliation report is needed.

## Legacy SQLite restore/import

If restoring from a historical SQLite export rather than a PostgreSQL backup,
use `docs/deployment/sqlite-migration.md`. The importer is temporary migration
tooling and should run only against empty rental business tables after Django
migrations.

