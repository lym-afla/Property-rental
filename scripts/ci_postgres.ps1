$ErrorActionPreference = "Stop"

$env:DJANGO_SETTINGS_MODULE = "property_rental.settings.test_postgres"

uv run python property_rental/manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run pytest --cov=rentals
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Keep the PostgreSQL-only importer behavior visible as an explicit CI gate.
uv run pytest property_rental/rentals/tests/test_migration_command.py -k postgresql
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run python property_rental/manage.py check --deploy --settings=property_rental.settings.prod
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
