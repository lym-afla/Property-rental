# SQLite-to-PostgreSQL migration notes

The normal production schema source is Django migrations applied to PostgreSQL:

```bash
python manage.py migrate --noinput
```

The temporary `import_sqlite` command exists only to import legacy application
data if an existing SQLite database must be carried into Life OS. It is not part
of normal startup and is not a permanent runtime contract.

## Preconditions

Run the importer only against a migrated PostgreSQL database whose rental
business tables are empty. Django system tables may already contain rows from
`migrate`, including migration history, content types, permissions, and
sessions.

The importer reads the SQLite source in read-only mode and writes only to the
configured Django destination database.

## Command

Mount the SQLite source file read-only into a one-shot job that uses the same
image and environment as production, then run:

```bash
python manage.py import_sqlite --source /import/rental.sqlite3 --report /import/reconciliation.json
```

For a validation-only pass:

```bash
python manage.py import_sqlite --source /import/rental.sqlite3 --report /import/reconciliation.json --dry-run
```

If only one legacy user should be carried forward, select that user's ownership
graph explicitly:

```bash
python manage.py import_sqlite \
  --source /import/rental.sqlite3 \
  --include-username Yaroslav \
  --report /import/reconciliation.json \
  --dry-run
```

Zero or multiple source users with the selected username fail closed. The same
selection option must be used for the real import after the dry-run report is
reviewed.

## Guarantees

The importer:

- validates that the SQLite schema has the expected application columns;
- imports application tables in dependency order;
- preserves application primary keys and foreign keys, because landlord,
  property, tenant, transaction, rent, valuation, and FX ownership relationships
  depend on them;
- wraps destination writes in a single transaction;
- preserves existing user rows for ownership continuity but sets unusable
  production passwords;
- resets PostgreSQL sequences after explicit-ID import;
- validates counts and relationships;
- produces a reconciliation report;
- can be rerun idempotently when the destination exactly matches the source.

If destination business tables contain non-matching data, the command fails
closed rather than merging or overwriting rows.

With `--include-username`, the importer:

- includes only the exactly matched source user, its landlord row, owned
  properties, property capital-structure rows, tenants, lease rents, and
  transactions;
- keeps global FX rows because cached exchange rates are shared reference data,
  not user-owned records;
- excludes other users and their dependent rental records;
- verifies that no included business row references an excluded user;
- preserves the selected user's primary key and ownership relationships;
- sets the selected user's Django password unusable;
- records the selection parameters and included/excluded counts per table in
  the reconciliation report.

## Imported users and OIDC linkage

Imported users are local ownership records. They are not automatically trusted
as production identities.

After import, link each intended user explicitly with verified Authentik values:

```bash
python manage.py link_oidc_identity \
  --user-id 123 \
  --issuer https://authentik.example/application/o/rent/ \
  --subject authentik-stable-subject
```

Never infer OIDC linkage from matching email alone. Email and username are
mutable profile attributes; the durable identity key is `(issuer, subject)`.

If an imported user cannot be unambiguously associated with the intended Life OS
identity, fail closed and leave that account unlinked until a verified mapping is
available.

After a linked user signs in through OIDC, Rent may update that local row's
mutable profile projection (`username`, `first_name`, `last_name`, `email`) from
verified Life OS claims. This does not change the imported primary key or any
landlord, property, tenant, transaction, rent, or valuation ownership
relationships.

