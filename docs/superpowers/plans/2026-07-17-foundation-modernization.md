# Foundation Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the security holes, extract a service layer, cache the FX graph, migrate SQLite→Postgres, stand up a DRF `/api/v1/` skeleton with a typed `/api/v1/chart-data/` endpoint, and establish a characterization test suite — without changing any user-visible behavior.

**Architecture:** Mechanical refactor of a Django 4.2 monolith. Business logic moves from `views.py` and god-models into a new `rentals/services/` package. DRF `ModelViewSet`s expose a per-user-scoped JSON API. Existing Django template pages keep working unchanged. Every financial calculation gets a characterization test pinning its current output *before* it is moved, so behavior cannot drift silently.

**Tech Stack:** Django 4.2.4, Django REST Framework 3.14, Postgres + psycopg v3, pytest + pytest-django + factory-boy, networkx (existing), yfinance (existing). Dev DB may stay SQLite; prod DB becomes Postgres.

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-07-17-foundation-modernization-design.md`):

- App is **personal / not live** — breaking changes are acceptable; no backwards-compat or zero-downtime constraints.
- Existing SQLite data is **migrated** (not disposed of) — a verified one-shot migration script is required.
- Strategic stack target: **Django + DRF backend, React + TypeScript + Vite + shadcn/ui + Recharts** frontend — but React is out of scope for this phase (Phase 3). This phase only adds the DRF API the later React app will consume.
- Sequencing: this is Phase 1 of 4. Phase 2 = charting rebuild, Phase 3 = frontend reshape, Phase 4 = architecture debt.
- **Out of scope:** React, chart UI changes, `Tenant` god-model dedup (`debt` vs `debt_advance_payment`), jQuery/DataTables removal, token/JWT auth, migrating every template endpoint to DRF.
- **Characterization tests must be green on the current SQLite DB before any refactor touches the code they pin.**
- Git identity (repo-local, already configured): `YL-STARDESTROYER <yaroslav.linik@gmail.com>`.
- Commit message style observed in repo: lowercase imperative (`fix: …`, `refactor: …`, `docs: …`).

## File Structure

### Files created

```
property_rental/property_rental/settings/
├── __init__.py            # empty, makes settings a package
├── base.py                # merged from settings.py: shared config
├── dev.py                 # DEBUG=True, SQLite, weak SECRET_KEY allowed
└── prod.py                # DEBUG=False, Postgres, SECRET_KEY from env

property_rental/rentals/services/
├── __init__.py            # empty
├── fx.py                  # FX graph cache + convert() + get_rate()
├── financials.py          # convert_transactions(), aggregate_financials()
├── charts.py              # get_chart_data() — moved from views.py
└── scheduler.py           # debt()/debt_advance_payment() — moved from Tenant model

property_rental/rentals/api/
├── __init__.py            # empty
├── serializers.py         # ModelSerializer per entity + ChartDataResponseSerializer
├── views.py               # ModelViewSet per entity + ChartDataView
└── permissions.py         # IsOwnerOrReadOnly (per-user queryset enforcement)

property_rental/rentals/tests/
├── __init__.py
├── conftest.py            # pytest fixtures: db, user factories, auth client
├── factories.py           # factory-boy: UserFactory, LandlordFactory, PropertyFactory, TenantFactory, TransactionFactory, FXFactory
├── test_security.py       # IDOR, missing-auth, global-state-removed
├── test_financials_char.py # characterization tests for debt/rent_total/financials/pnl
├── test_fx_char.py        # characterization tests for FX.get_rate (pins pre-migration output)
├── test_fx_migration.py   # wide→long schema migration: data preserved, get_rate output unchanged
├── test_charts_char.py    # characterization tests for get_chart_data
├── test_services.py       # unit tests for the new service modules
└── test_api.py            # DRF endpoint happy-path + auth-failure tests

property_rental/scripts/
└── migrate_sqlite_to_postgres.py   # one-shot verified migration

.github/workflows/
└── ci.yml                 # pytest --cov on push/PR; matrix Python 3.11, 3.12

pyproject.toml             # pytest config + tool config
requirements-dev.txt       # pytest, pytest-django, factory-boy, coverage, psycopg[binary]
```

### Files modified (and how)

| File | Change |
|---|---|
| `property_rental/property_rental/settings.py` | **Deleted.** Content split into `settings/{base,dev,prod}.py`. |
| `property_rental/manage.py` | `DJANGO_SETTINGS_MODULE` defaults to `property_rental.settings.dev`. |
| `property_rental/property_rental/wsgi.py` | `DJANGO_SETTINGS_MODULE` defaults to `property_rental.settings.prod`. |
| `.gitignore` | Remove lines 14-16 (test exclusions) and line 19 (settings exclusion). |
| `property_rental/requirements.txt` | Add `psycopg[binary]`, `djangorestframework>=3.14`, confirm `networkx`, `yfinance`. |
| `property_rental/rentals/models.py` | `FX` model migrated from wide (per-pair columns `EURUSD`/`GBPUSD`/`USDRUB`) to long format (`from_currency`, `to_currency`, `rate`, `date`). `FX.update_fx_rates/get_rate` → thin delegates to `services.fx`. `Tenant.debt/debt_advance_payment` → thin delegates to `services.scheduler`. `Transaction.financials` → delegates to `services.financials`. Add `User.effective_date` field + migration. Remove `FX.__tablename__`. |
| `property_rental/rentals/views.py` | Replace inline business logic with service calls. Add `@login_required` to 6 views. Add ownership check to DELETE branch of `handle_element`. Add `case _:` default. Remove global-state handling for `effective_current_date`. Target: shed ≥300 lines. |
| `property_rental/rentals/utils.py` | Remove `effective_current_date` global. Fix `calculate_from_date` `months=` bug. |
| `property_rental/rentals/urls.py` | Remove `# TO BE DELETED` routes. Add `path('api/v1/', include('rentals.api.urls'))`. |
| `property_rental/rentals/templates/rentals/layout.html` | Remove navbar date picker (lines 57-58). Add SRI hashes to CDN tags. |
| `property_rental/rentals/templates/rentals/index.html`, `properties.html`, `tenants.html` | Add SRI hashes to Chart.js CDN tags. |

---

## Task Ordering

The tasks are sequenced so the characterization test net is in place *before* any refactor that could change behavior. Nine phases:

1. **Settings + gitignore + deps + CI scaffold** (Task 1) — makes tests trackable and runnable.
2. **Characterization test capture** (Tasks 2-5) — pins every financial calc against the *current* codebase, green baseline. No production code changes.
3. **Security fixes** (Tasks 6-8) — IDOR, auth, global-state removal. Each has an asserting test.
4. **FX schema migration** (Task 9) — migrate the wide `FX` table (one column per pair: `EURUSD`/`GBPUSD`/`USDRUB`) to normalized long format (`from_currency`, `to_currency`, `rate`). Gated by the Task 4 FX characterization tests — must preserve every rate value and every `get_rate` output.
5. **FX cache** (Task 10) — the big perf win, now trivial because the long schema eliminates field introspection.
6. **Service layer extraction** (Tasks 11-14) — mechanical moves of fx, financials, charts, scheduler. Characterization tests stay green throughout.
7. **Postgres migration** (Task 15) — script + verification.
8. **DRF API** (Tasks 16-18) — endpoints, serializers, per-user querysets.
9. **Verification** (Task 19) — full definition-of-done check.

---

## Task 1: Settings split, gitignore, deps, pytest scaffold, CI

**Files:**
- Create: `property_rental/property_rental/settings/__init__.py`, `base.py`, `dev.py`, `prod.py`
- Create: `pyproject.toml`, `requirements-dev.txt`, `.github/workflows/ci.yml`
- Modify: `property_rental/manage.py`, `property_rental/property_rental/wsgi.py`, `.gitignore`
- Delete: `property_rental/property_rental/settings.py`

**Interfaces:**
- Produces: `property_rental.settings.dev` and `property_rental.settings.prod` as importable settings modules; `pytest` runnable from repo root.

- [ ] **Step 1: Un-gitignore tests and settings**

In `.gitignore`, remove these three lines (currently lines 14-16 and 19):
```
property_rental/tests/
test_*.py
testing.py
```
and:
```
property_rental/property_rental/settings.py
```

- [ ] **Step 2: Split settings.py into a package**

Create `property_rental/property_rental/settings/__init__.py` (empty). Move the entire current `settings.py` content into `settings/base.py`. Then in `base.py`:
- Remove `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, and `DATABASES` (these move to dev/prod).
- Keep `INSTALLED_APPS`, `MIDDLEWARE`, `TEMPLATES`, `AUTH_USER_MODEL`, `STATIC_*`, `LANGUAGE_CODE`, `TIME_ZONE`, `USE_TZ`, password validators (re-enabled — see Step 5).

Create `settings/dev.py`:
```python
from .base import *  # noqa
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-prod"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

Create `settings/prod.py`:
```python
import os
from .base import *  # noqa
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # raises KeyError if missing — intentional
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DJANGO_DB_NAME"],
        "USER": os.environ["DJANGO_DB_USER"],
        "PASSWORD": os.environ["DJANGO_DB_PASSWORD"],
        "HOST": os.environ.get("DJANGO_DB_HOST", "localhost"),
        "PORT": os.environ.get("DJANGO_DB_PORT", "5432"),
    }
}
```

- [ ] **Step 3: Point manage.py and wsgi.py at the new modules**

In `manage.py`, change the default to `property_rental.settings.dev`. In `property_rental/property_rental/wsgi.py`, change the default to `property_rental.settings.prod`.

- [ ] **Step 4: Re-enable password validators in base.py**

In `settings/base.py`, uncomment all four `AUTH_PASSWORD_VALIDATORS` entries (`UserAttributeAttributeValidator`, `MinimumLengthValidator`, `CommonPasswordValidator`, `NumericPasswordValidator`).

- [ ] **Step 5: Delete the old single-file settings.py**

`git rm property_rental/property_rental/settings.py`.

- [ ] **Step 6: Add dev dependencies**

Create `requirements-dev.txt`:
```
-r requirements.txt
pytest>=7.4
pytest-django>=4.7
factory-boy>=3.3
coverage>=7.3
psycopg[binary]>=3.1
```
Add `djangorestframework>=3.14` and `psycopg[binary]>=3.1` to the main `requirements.txt` too (prod needs them).

- [ ] **Step 7: Configure pytest**

Create `pyproject.toml`:
```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "property_rental.settings.dev"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
```

- [ ] **Step 8: Add CI workflow**

Create `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements-dev.txt
        working-directory: property_rental
      - run: pytest --cov=rentals
        working-directory: property_rental
```

- [ ] **Step 9: Verify Django still boots**

Run from `property_rental/`: `python manage.py check`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: split settings into base/dev/prod, un-gitignore tests, add pytest scaffold and CI"
```

---

## Task 2: Characterization test fixtures and factories

**Files:**
- Create: `property_rental/rentals/tests/__init__.py`, `conftest.py`, `factories.py`
- Create: `property_rental/rentals/migrations/` (auto-generated for the factory pattern; no schema change yet)

**Interfaces:**
- Produces: `UserFactory`, `LandlordFactory`, `PropertyFactory`, `TenantFactory`, `TransactionFactory`, `FXFactory`, plus pytest fixtures `landlord_user`, `other_landlord_user`, `auth_client`, `sample_property`.

- [ ] **Step 1: Create the tests package and conftest**

`rentals/tests/__init__.py` empty. `rentals/tests/conftest.py`:
```python
import pytest
from django.test import Client
from rentals.tests.factories import (
    LandlordFactory, UserFactory, PropertyFactory, TenantFactory, TransactionFactory, FXFactory,
)

@pytest.fixture
def landlord_user(db):
    user = UserFactory(is_landlord=True)
    LandlordFactory(user=user)
    return user

@pytest.fixture
def other_landlord_user(db):
    user = UserFactory(is_landlord=True)
    LandlordFactory(user=user)
    return user

@pytest.fixture
def auth_client(db, landlord_user):
    c = Client()
    c.force_login(landlord_user)
    return c

@pytest.fixture
def sample_property(db, landlord_user):
    return PropertyFactory(owned_by=landlord_user.landlord)
```

- [ ] **Step 2: Write factory-boy factories**

`rentals/tests/factories.py` — one `factory.django.DjangoModelFactory` per model. Key fields with sensible defaults; foreign keys delegate to subfactories. **Do not** set `amount`, `currency`, `category`, `date` to constants — the characterization tests need to vary these. Use `factory.Faker` for non-financial fields and leave financial fields unset (caller-provided).

Skeleton:
```python
import factory
from rentals.models import User, Landlord, Property, Tenant, Transaction, FX, Property_capital_structure, Lease_rent

class UserFactory(factory.django.DjangoModelFactory):
    class Meta: model = User
    username = factory.Sequence(lambda n: f"user{n}")
    is_landlord = True

class LandlordFactory(factory.django.DjangoModelFactory):
    class Meta: model = Landlord
    user = factory.SubFactory(UserFactory)

class PropertyFactory(factory.django.DjangoModelFactory):
    class Meta: model = Property
    owned_by = factory.SubFactory(LandlordFactory)
    # leave name, currency, address to caller or Faker

# ... Tenant, Transaction, FX, Property_capital_structure, Lease_rent factories
```

Consult `rentals/models.py` for the exact required fields per model before completing each factory. Every non-nullable field without a model default must be set in the factory.

- [ ] **Step 3: Smoke-test the factories**

Write `rentals/tests/test_factories_smoke.py`:
```python
def test_factories_create_valid_instances(db):
    from rentals.tests.factories import (
        UserFactory, LandlordFactory, PropertyFactory, TenantFactory, TransactionFactory, FXFactory,
    )
    assert UserFactory().pk
    assert PropertyFactory().pk
    # ... one assert per factory
```
Run `pytest rentals/tests/test_factories_smoke.py -v`. All must pass against the current DB.

- [ ] **Step 4: Commit**

```bash
git add rentals/tests/
git commit -m "test: add pytest fixtures and factory-boy factories"
```

---

## Task 3: Characterization tests for financial calculations

**Goal:** Pin the current output of `Tenant.debt`, `Tenant.debt_advance_payment`, `Tenant.rent_total`, `Transaction.financials`, and `pnl_calc` against known inputs. **No production code changes.** These tests are the safety net for Tasks 9-13.

**Files:**
- Create: `property_rental/rentals/tests/test_financials_char.py`

**Interfaces:**
- Consumes: factories from Task 2.
- Produces: a green baseline that must remain green after Tasks 9-13.

**Approach:** Golden-master style. Build a small, deterministic dataset (a property, a tenant, a lease_rent rate, and a handful of transactions with known dates/amounts/currencies). Call each calculation and assert the exact numeric result. Capture the current value by running once with `--pdb` or a print; encode it as the expected value.

- [ ] **Step 1: Build a deterministic financial scenario**

In `test_financials_char.py`, write a fixture/helper `build_arrears_scenario()` that creates:
- 1 property, currency `USD`.
- 1 tenant with `lease_start` 6 months ago, monthly rent `$1000`, due-day-of-month = 1, grace period = 5 days.
- 3 rent transactions: one on-time, one within grace, one late (in arrears).
- Cross-currency variant: a second tenant with `GBP` transactions against a `USD` property, with at least one `FX` row for `GBPUSD`.

- [ ] **Step 2: Capture golden values**

Write the test functions as `assert actual == EXPECTED` with `EXPECTED` initially a placeholder `0`. Run them. Read the actual output from the failure. Replace `0` with the captured value. Re-run to confirm green.

Tests to write (one per method):
- `test_tenant_debt_arrears_scenario` — `Tenant.debt(...)` on the arrears scenario.
- `test_tenant_debt_advance_payment_scenario` — `Tenant.debt_advance_payment(...)` on the same scenario.
- `test_tenant_rent_total_same_currency` — `Tenant.rent_total(...)` on the USD-only transactions.
- `test_tenant_rent_total_cross_currency` — `Tenant.rent_total(...)` on the GBP scenario (uses FX).
- `test_transaction_financials_aggregation` — `Transaction.financials(...)` for the property.
- `test_pnl_calc_portfolio` — `pnl_calc(...)` for the landlord (import from `rentals.views`).

- [ ] **Step 3: Run and capture**

Run `pytest rentals/tests/test_financials_char.py -v`. Iterate on `EXPECTED` values until all pass. These are now the contract.

- [ ] **Step 4: Commit**

```bash
git add rentals/tests/test_financials_char.py
git commit -m "test: pin financial calculations with golden-master characterization tests"
```

---

## Task 4: Characterization tests for FX

**Goal:** Pin `FX.get_rate` for direct pairs and multi-hop conversions, and pin the cross-currency outputs that depend on it.

**Files:**
- Create: `property_rental/rentals/tests/test_fx_char.py`

- [ ] **Step 1: Build FX dataset**

Helper `build_fx_graph()` creates FX rows forming a small graph: `EUR→USD=1.10`, `GBP→USD=1.25`, `EUR→GBP=0.88`, plus a 2-hop case (`RUB` via `EUR`). All rates dated within the test's as-of date.

- [ ] **Step 2: Capture golden values for `FX.get_rate`**

Tests:
- `test_get_rate_direct` — `FX.get_rate("EUR", "USD", as_of)` returns the direct rate.
- `test_get_rate_reverse` — `FX.get_rate("USD", "EUR", as_of)` returns the reciprocal.
- `test_get_rate_two_hop` — `FX.get_rate("EUR", "RUB", as_of)` uses Bellman-Ford across 2 hops; capture the exact value.
- `test_get_rate_no_path` — `FX.get_rate("USD", "JPY", as_of)` with no JPY rows; assert current behavior (raises? returns None? — pin whatever it does today).

Capture and encode the same way as Task 3.

- [ ] **Step 3: Commit**

```bash
git add rentals/tests/test_fx_char.py
git commit -m "test: pin FX.get_rate for direct, reverse, and multi-hop conversions"
```

---

## Task 5: Characterization tests for chart data

**Goal:** Pin `get_chart_data` output for `homePage`, `property`, and `tenant` types.

**Files:**
- Create: `property_rental/rentals/tests/test_charts_char.py`

- [ ] **Step 1: Build dataset with enough transactions to produce non-trivial chart output**

Reuse factories; create transactions spanning 6+ months across multiple categories (rent, utilities, etc.) so the home chart has multiple datasets.

- [ ] **Step 2: Capture golden payloads**

Tests:
- `test_get_chart_data_homepage_monthly` — `get_chart_data("homePage", landlord_id, "M", start, end, "USD", None)`.
- `test_get_chart_data_homepage_yearly` — same with `"Y"`.
- `test_get_chart_data_property` — `get_chart_data("property", property_id, "M", start, end, "USD", None)`.
- `test_get_chart_data_tenant` — `get_chart_data("tenant", tenant_id, "Q", start, end, "USD", None)`.

Each asserts the full `{labels, datasets, currency}` dict deep-equals a captured expected. Use `json.dumps(actual, sort_keys=True)` comparison if easier.

- [ ] **Step 3: Commit**

```bash
git add rentals/tests/test_charts_char.py
git commit -m "test: pin get_chart_data output for homePage/property/tenant chart types"
```

---

## Task 6: DELETE IDOR fix

**Files:**
- Modify: `property_rental/rentals/views.py:616-618` (DELETE branch of `handle_element`)
- Test: `property_rental/rentals/tests/test_security.py`

**Interfaces:**
- Produces: ownership check enforced on DELETE, matching GET/PUT.

- [ ] **Step 1: Write the failing security test**

`rentals/tests/test_security.py`:
```python
import pytest
from django.urls import reverse

def test_landlord_cannot_delete_other_landlords_property(auth_client, sample_property, other_landlord_user):
    # sample_property is owned by landlord_user (the auth_client's user).
    # Attempt to delete it as other_landlord_user's session.
    from django.test import Client
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "property", "element_id": sample_property.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # Confirm the property still exists
    from rentals.models import Property
    assert Property.objects.filter(pk=sample_property.pk).exists()
```

- [ ] **Step 2: Run, confirm failure (403 not yet returned)**

Run: `pytest rentals/tests/test_security.py::test_landlord_cannot_delete_other_landlords_property -v`
Expected: FAIL (current code deletes unconditionally; property is gone, status 200).

- [ ] **Step 3: Add the ownership check**

In `views.py`, the DELETE branch of `handle_element` (around line 616). Match the GET/PUT pattern:
```python
elif request.method == 'DELETE':
    if element.owned_by.user != request.user:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    element.delete()
    return JsonResponse({'message': f'{data_type} deleted successfully'}, status=200)
```

- [ ] **Step 4: Run, confirm pass**

Run the same test. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rentals/views.py rentals/tests/test_security.py
git commit -m "fix: enforce ownership check on DELETE to close IDOR (CVE-class)"
```

---

## Task 7: Add `@login_required` to unauthenticated views and scope `update_fx_view`

**Files:**
- Modify: `property_rental/rentals/views.py` — decorators on `update_date`, `update_fx_view`, `property_choices`, `chart_data_request`, `new_form`, `fx_list`.
- Modify: `update_fx_view` body — restrict the property queryset to the requesting user.
- Test: `property_rental/rentals/tests/test_security.py`

- [ ] **Step 1: Write failing auth tests**

Append to `test_security.py`:
```python
@pytest.mark.parametrize("url_name", ["rentals:update_fx_view", "rentals:fx_list", "rentals:property_choices"])
def test_unauthenticated_request_redirected_to_login(db, client, url_name):
    url = reverse(url_name)
    resp = client.get(url)
    assert resp.status_code in (302, 401, 403)
    if resp.status_code == 302:
        assert "/login" in resp.url or "/accounts/login" in resp.url
```

- [ ] **Step 2: Run, confirm failures**

- [ ] **Step 3: Add the decorators**

Add `@login_required` (already imported at top of `views.py`) to each of the 6 named views.

- [ ] **Step 4: Scope `update_fx_view` to the requesting user**

In `update_fx_view`, replace the unscoped `Property.objects.all()` (or equivalent) with:
```python
properties = Property.objects.filter(owned_by__user=request.user)
```

- [ ] **Step 5: Run, confirm pass; then run the full characterization suite**

Run: `pytest rentals/tests/ -v`. All char tests + new security tests must pass.

- [ ] **Step 6: Commit**

```bash
git add rentals/views.py rentals/tests/test_security.py
git commit -m "fix: require auth on FX/property/chart endpoints; scope update_fx to requesting user"
```

---

## Task 8: Remove process-global `effective_current_date`; add `User.effective_date`

**Files:**
- Modify: `property_rental/rentals/models.py` — add `effective_date = DateField(null=True, blank=True)` to `User`.
- Create: migration for the new field.
- Modify: `property_rental/rentals/utils.py` — remove `effective_current_date` global; add `get_effective_date(user)` helper returning `user.effective_date or date.today()`.
- Modify: `property_rental/rentals/views.py` — replace reads of the global with `get_effective_date(request.user)`. Remove the `update_date` view (its route was removed in Task 1's urls cleanup; if still present, remove).
- Modify: `property_rental/rentals/templates/rentals/layout.html:57-58` — remove the navbar date picker.
- Test: `property_rental/rentals/tests/test_security.py`

- [ ] **Step 1: Write failing test for per-user isolation**

```python
def test_effective_date_is_per_user(db, landlord_user, other_landlord_user):
    from rentals.utils import get_effective_date
    from datetime import date
    landlord_user.effective_date = date(2024, 1, 1)
    landlord_user.save()
    other_landlord_user.effective_date = date(2025, 6, 1)
    other_landlord_user.save()
    assert get_effective_date(landlord_user) == date(2024, 1, 1)
    assert get_effective_date(other_landlord_user) == date(2025, 6, 1)
```

- [ ] **Step 2: Run, confirm fails (global still in place)**

- [ ] **Step 3: Add the field + migration**

```bash
python manage.py makemigrations rentals
python manage.py migrate
```

- [ ] **Step 4: Remove the global and add the helper**

In `utils.py`: delete `effective_current_date = ...` (line ~10). Add:
```python
from datetime import date
def get_effective_date(user):
    return getattr(user, "effective_date", None) or date.today()
```

- [ ] **Step 5: Replace global reads in views**

Grep `views.py` for `effective_current_date` and replace each with `get_effective_date(request.user)`. Remove the `update_date` view function entirely.

- [ ] **Step 6: Remove the navbar date picker from layout.html**

Delete lines 57-58 (the `<input type="date">` + button). Remove the `update_date` route from `urls.py` if still present.

- [ ] **Step 7: Run all tests**

`pytest rentals/tests/ -v`. Char suite must still be green (behavior unchanged for `today` default).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "fix: replace process-global as-of date with per-user User.effective_date field"
```

---

## Task 9: Migrate `FX` schema from wide (per-pair columns) to long format

**Goal:** Replace the anti-pattern `FX` table (one `DecimalField` column per currency pair: `EURUSD`, `GBPUSD`, `USDRUB`) with the normalized long format (`from_currency`, `to_currency`, `rate`, `date`). Adding a new currency pair must become a new **row**, not a schema migration. The graph builder in `FX.get_rate` currently introspects `_meta.fields` and parses column names at runtime to discover edges — the long format eliminates that fragility entirely.

This is gated by Task 4's `test_fx_char.py`: after the migration, every `FX.get_rate(...)` call must return the **exact same value** as before. The characterization tests are the proof that the migration is value-preserving.

**Files:**
- Modify: `property_rental/rentals/models.py` — redefine `FX` fields: drop `EURUSD`/`GBPUSD`/`USDRUB` columns, add `from_currency` (`CharField(max_length=3)`), `to_currency` (`CharField(max_length=3)`), `rate` (`DecimalField`). Keep `date`. Remove `FX.__tablename__ = 'FX'` (SQLAlchemy-ism).
- Create: migration for the schema change + a `RunPython` data migration that backfills existing wide rows into long rows (see Step 3).
- Modify: `property_rental/rentals/models.py` — rewrite `FX.get_rate` and `FX.update_fx_rates` to read the long-format columns (see Step 4). The field-introspection loop becomes a plain `for fx in FX.objects.filter(date__lte=as_of): g.add_edge(fx.from_currency, fx.to_currency, weight=fx.rate)`.
- Modify: `property_rental/rentals/utils.py` — `update_FX_database()` (the yfinance fetcher) must write long-format rows.
- Modify: `property_rental/rentals/tests/factories.py` — `FXFactory` produces long-format rows (`from_currency`, `to_currency`, `rate`, `date`).
- Test: `property_rental/rentals/tests/test_fx_migration.py`

**Interfaces:**
- Consumes: the Task 4 FX characterization tests (`test_fx_char.py`), which pin `get_rate` output on the wide schema.
- Produces: a long-format `FX` model whose `get_rate` returns identical values for the same logical rates. Tasks 10 (cache), 11 (services), and the DRF serializer all consume the long format.

- [ ] **Step 1: Write a migration-correctness test**

`rentals/tests/test_fx_migration.py`:
```python
from datetime import date
from decimal import Decimal
import pytest
from rentals.models import FX

@pytest.mark.django_db
def test_fx_model_has_long_format_fields():
    """Schema migration: FX must have from_currency/to_currency/rate, not per-pair columns."""
    field_names = {f.name for f in FX._meta.get_fields()}
    assert "from_currency" in field_names
    assert "to_currency" in field_names
    assert "rate" in field_names
    assert "EURUSD" not in field_names
    assert "GBPUSD" not in field_names
    assert "USDRUB" not in field_names

@pytest.mark.django_db
def test_fx_get_rate_unchanged_after_migration():
    """get_rate must return the same value as before the wide→long migration.
    This re-asserts what test_fx_char.py pins, but against the long schema,
    so a regression here proves the migration drifted."""
    FX.objects.create(date=date(2024,1,15), from_currency="EUR", to_currency="USD", rate=Decimal("1.08"))
    FX.objects.create(date=date(2024,1,15), from_currency="GBP", to_currency="USD", rate=Decimal("1.25"))
    rate = FX.get_rate("EUR", "USD", as_of=date(2024,2,1))
    assert rate == Decimal("1.08")  # adjust to whatever the real algorithm returns
```
(Adjust the final assertion's expected value to match what `test_fx_char.py` captured — the point is identical output, same algorithm.)

- [ ] **Step 2: Run, confirm fails (still wide format)**

Run: `pytest rentals/tests/test_fx_migration.py -v`
Expected: FAIL — `from_currency`/`to_currency`/`rate` fields don't exist yet.

- [ ] **Step 3: Schema + data migration**

Add the new fields to the `FX` model in `models.py` (with `null=True, blank=True` initially so the data migration can populate them):
```python
class FX(models.Model):
    date = models.DateField()
    from_currency = models.CharField(max_length=3, null=True, blank=True)
    to_currency = models.CharField(max_length=3, null=True, blank=True)
    rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    # OLD columns kept temporarily for the data migration:
    EURUSD = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    GBPUSD = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    USDRUB = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
```
Generate the schema migration: `python manage.py makemigrations rentals`.

Then write a **data migration** (`migrations/00XX_fx_wide_to_long.py`) with a `RunPython` that, for each existing FX row, emits one long row per non-null pair column:
```python
def forwards(apps, schema_editor):
    FX = apps.get_model("rentals", "FX")
    for fx in FX.objects.all():
        for pair_col, base, quote in [("EURUSD","EUR","USD"), ("GBPUSD","GBP","USD"), ("USDRUB","USD","RUB")]:
            rate = getattr(fx, pair_col)
            if rate is not None:
                FX.objects.create(date=fx.date, from_currency=base, to_currency=quote, rate=rate)
        fx.delete()  # remove the old wide row
```
Run: `python manage.py migrate`.

**Then** a follow-up migration drops the old columns and tightens the new ones to non-nullable (after confirming all rows are populated). Re-edit the model to remove `EURUSD`/`GBPUSD`/`USDRUB` and drop `null=True` from the new fields; `makemigrations` again; `migrate`.

- [ ] **Step 4: Rewrite `FX.get_rate` and `FX.update_fx_rates` for long format**

In `models.py`, `FX.get_rate`'s graph-build loop (the part that currently introspects `_meta.fields` and parses column names) becomes:
```python
g = nx.Graph()
for fx in FX.objects.filter(date__lte=as_of):
    g.add_edge(fx.from_currency, fx.to_currency, weight=float(fx.rate))
```
The rest of the Bellman-Ford traversal stays verbatim — same algorithm, same return values.

`FX.update_fx_rates` (and `utils.update_FX_database`) must write `FX(from_currency=..., to_currency=..., rate=..., date=...)` rows instead of setting pair columns. Trace every call site and update.

- [ ] **Step 5: Update `FXFactory`**

In `rentals/tests/factories.py`, redefine `FXFactory` to set `from_currency`/`to_currency`/`rate`/`date` (drop the pair-column attrs).

- [ ] **Step 6: Run ALL characterization tests — they MUST stay green**

Run: `pytest rentals/tests/test_fx_char.py rentals/tests/test_fx_migration.py rentals/tests/test_financials_char.py rentals/tests/test_charts_char.py -v`
Expected: all green. If `test_fx_char.py` fails, the migration changed `get_rate` output — that's a regression; fix before proceeding.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: migrate FX table from wide (per-pair columns) to normalized long format"
```

---

## Task 10: FX graph cache

**Goal:** Build the networkx graph once per process (invalidated on `FX` save/delete) instead of per `get_rate` call. The biggest perf win in the phase. Gated by `test_fx_char.py` — output must not change.

**Files:**
- Create: `property_rental/rentals/services/__init__.py`, `services/fx.py`
- Modify: `property_rental/rentals/models.py` — `FX.get_rate` and `FX.update_fx_rates` delegate to `services.fx`; `FX.save`/`FX.delete` invalidate the cache.

**Interfaces:**
- Produces: `services.fx.get_rate(from_currency, to_currency, as_of)`, `services.fx.convert(amount, from_currency, to_currency, as_of)`, `services.fx.invalidate_cache()`.

- [ ] **Step 1: Write a test asserting cache is built ≤1 time per request**

`rentals/tests/test_services.py`:
```python
from unittest.mock import patch
from rentals.services import fx as fx_service

def test_fx_graph_is_cached(db):
    build_graph = fx_service.build_graph
    with patch.object(fx_service, "build_graph", wraps=build_graph) as spy:
        fx_service.get_rate("EUR", "USD", as_of=__import__("datetime").date.today())
        fx_service.get_rate("EUR", "USD", as_of=__import__("datetime").date.today())
        fx_service.get_rate("GBP", "USD", as_of=__import__("datetime").date.today())
        assert spy.call_count <= 1, f"graph rebuilt {spy.call_count} times; expected cache hit"
```
(Setup: create FX rows first via factory so the graph is non-empty.)

- [ ] **Step 2: Run, confirm fails (no cache yet)**

- [ ] **Step 3: Implement the cache**

`rentals/services/fx.py`:
```python
import networkx as nx
from datetime import date
from rentals.models import FX

_graph_cache = {"graph": None, "as_of": None}

def build_graph(as_of):
    g = nx.Graph()
    for fx in FX.objects.filter(date__lte=as_of):
        g.add_edge(fx.from_currency, fx.to_currency, weight=fx.rate)
    return g

def _get_graph(as_of):
    if _graph_cache["graph"] is None or _graph_cache["as_of"] != as_of:
        _graph_cache["graph"] = build_graph(as_of)
        _graph_cache["as_of"] = as_of
    return _graph_cache["graph"]

def invalidate_cache():
    _graph_cache["graph"] = None
    _graph_cache["as_of"] = None

def get_rate(from_currency, to_currency, as_of):
    # Preserve exact current behavior of FX.get_rate (Bellman-Ford path).
    # ...moved verbatim from models.py FX.get_rate, using _get_graph(as_of)
    pass

def convert(amount, from_currency, to_currency, as_of):
    if from_currency == to_currency:
        return amount
    return amount * get_rate(from_currency, to_currency, as_of)
```

Move the body of `FX.get_rate` (`models.py:521-591`) verbatim into `services.fx.get_rate`, swapping the `nx.Graph()` construction call for `_get_graph(as_of)`. **Do not change the algorithm or the return values** — the char tests must stay green.

- [ ] **Step 4: Wire `FX.save`/`delete` to invalidate, and make `FX.get_rate` delegate**

In `models.py`:
```python
class FX(models.Model):
    # ... existing fields ...
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from rentals.services import fx as fx_service
        fx_service.invalidate_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from rentals.services import fx as fx_service
        fx_service.invalidate_cache()

    @classmethod
    def get_rate(cls, from_currency, to_currency, as_of):
        from rentals.services.fx import get_rate as _get_rate
        return _get_rate(from_currency, to_currency, as_of)
```
Preserve `FX.update_fx_rates` similarly (delegate to a `services.fx.update_rates()` that wraps the existing yfinance logic verbatim).

- [ ] **Step 5: Run the FX char tests — they MUST stay green**

Run: `pytest rentals/tests/test_fx_char.py rentals/tests/test_financials_char.py -v`
Expected: all green (same outputs).

- [ ] **Step 6: Run the cache test — must pass**

Run: `pytest rentals/tests/test_services.py::test_fx_graph_is_cached -v`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "perf: cache FX networkx graph; build once per as_of instead of per get_rate call"
```

---

## Task 11: Extract `services/financials.py`

**Goal:** Move `pnl_calc` and `Transaction.financials` aggregation into a service. Consolidate the four duplicated currency-conversion loops into one helper. **Characterization tests must stay green.**

**Files:**
- Create: `property_rental/rentals/services/financials.py`
- Modify: `property_rental/rentals/models.py` — `Transaction.financials` delegates.
- Modify: `property_rental/rentals/views.py` — `pnl_calc` delegates (or is removed and callers import the service).

**Interfaces:**
- Produces: `services.financials.convert_transactions(qs, target_currency, as_of)`, `services.financials.aggregate(qs, target_currency, as_of)`, `services.financials.pnl_calc(landlord, ...)`.

- [ ] **Step 1: Write a thin unit test for `convert_transactions`**

In `test_services.py`:
```python
def test_convert_transactions_same_currency_skips_fx(db, sample_property):
    from rentals.services.financials import convert_transactions
    from rentals.tests.factories import TransactionFactory
    from datetime import date
    txns = [TransactionFactory(property=sample_property, amount=100, currency="USD"),
            TransactionFactory(property=sample_property, amount=200, currency="USD")]
    total = convert_transactions(txns, "USD", date.today())
    assert total == 300
```

- [ ] **Step 2: Implement `services.financials`**

Move the aggregation logic from `Transaction.financials` (`models.py:402-456`) verbatim into `aggregate()`. Implement `convert_transactions` to use `services.fx.convert` per row when currencies differ (preserving current behavior). Move `pnl_calc` (`views.py:997-1051`) into `services.financials.pnl_calc` verbatim.

- [ ] **Step 3: Make `Transaction.financials` and `pnl_calc` delegates**

`Transaction.financials` becomes a `@classmethod` that calls `services.financials.aggregate(...)`. The `pnl_calc` function in `views.py` either becomes a one-line delegate or callers import the service directly.

- [ ] **Step 4: Run all characterization tests**

Run: `pytest rentals/tests/test_financials_char.py rentals/tests/test_charts_char.py -v`
Expected: green (unchanged outputs).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: extract financial aggregation into services.financials"
```

---

## Task 12: Extract `services/charts.py` and fix `property_valuation` hardcoded params

**Files:**
- Create: `property_rental/rentals/services/charts.py`
- Modify: `property_rental/rentals/views.py` — `get_chart_data` delegates; `property_valuation` view now reads params from request.
- Modify: `property_rental/rentals/views.py:1066` — replace hardcoded `'M'`, `'2022-06-01'`, `'2023-09-15'`, `'USD'` with request/session-derived values.

**Interfaces:**
- Produces: `services.charts.get_chart_data(type, id, freq, start, end, currency, landlord)` returning the `{labels, datasets, currency}` dict.

- [ ] **Step 1: Move `get_chart_data` verbatim into `services.charts`**

Move `views.py:871-993` into `services/charts.py`. Adjust imports. The function's body is unchanged.

- [ ] **Step 2: Replace inline references in `views.py`**

Wherever `get_chart_data(...)` was called in `views.py` (the `index` view, `handle_element`, `chart_data_request`, `property_valuation`), import and call `services.charts.get_chart_data(...)`.

- [ ] **Step 3: Fix the `property_valuation` hardcoded params**

In the `property_valuation` view, replace:
```python
data = get_chart_data('property', property_id, 'M', '2022-06-01', '2023-09-15', 'USD', None)
```
with reading from `request.GET`/`request.session`:
```python
settings = request.session.get("chart_settings", {})
freq = request.GET.get("freq", settings.get("freq", "M"))
start = request.GET.get("start", settings.get("start"))
end = request.GET.get("end", settings.get("end"))
currency = request.GET.get("currency", settings.get("currency", "USD"))
data = get_chart_data("property", property_id, freq, start, end, currency, None)
```

- [ ] **Step 4: Run char tests + add a regression test**

Add `test_property_valuation_uses_request_params` to `test_charts_char.py` asserting the endpoint returns data for a non-2022-2023 window when requested via query params.

Run: `pytest rentals/tests/ -v`. All green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: extract get_chart_data into services.charts; fix property_valuation hardcoded params"
```

---

## Task 13: Extract `services/scheduler.py`

**Goal:** Move `Tenant.debt` and `Tenant.debt_advance_payment` verbatim into a service. **No dedup** — both move separately (Phase 4 unifies them). Char tests must stay green.

**Files:**
- Create: `property_rental/rentals/services/scheduler.py`
- Modify: `property_rental/rentals/models.py` — `Tenant.debt` and `Tenant.debt_advance_payment` delegate.

**Interfaces:**
- Produces: `services.scheduler.debt(tenant, ...)`, `services.scheduler.debt_advance_payment(tenant, ...)`.

- [ ] **Step 1: Move both methods verbatim**

Copy the bodies of `Tenant.debt` (`models.py:180-263`) and `Tenant.debt_advance_payment` (`:266-363`) into `services/scheduler.py` as standalone functions taking `tenant` as the first arg. Replace `self` references with `tenant`.

- [ ] **Step 2: Make the model methods delegates**

```python
def debt(self, ...):
    from rentals.services.scheduler import debt as _debt
    return _debt(self, ...)
```
Same for `debt_advance_payment`.

- [ ] **Step 3: Run char tests**

Run: `pytest rentals/tests/test_financials_char.py -v`. Green.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: extract Tenant.debt/debt_advance_payment into services.scheduler"
```

---

## Task 14: Fix `calculate_from_date` YTD bug, add `case _:` default, remove dead code

**Files:**
- Modify: `property_rental/rentals/utils.py:255` — `to_date.replace(months=1, day=1)` → `to_date + relativedelta(months=1)` then set day, or use `date(to_date.year, 1, 1)`.
- Modify: `property_rental/rentals/views.py:432` — add `case _: return JsonResponse({"error": "unknown type"}, status=400)` to the outer `match`.
- Modify: `property_rental/rentals/models.py` — remove `FX.__tablename__ = 'FX'` (line 474).
- Modify: `property_rental/requirements.txt` — remove `peewee` if grep confirms no imports.
- Run `grep -rn "import peewee\|from peewee" property_rental/` to confirm before removing.

- [ ] **Step 1: Write a test for the YTD branch**

```python
def test_calculate_from_date_ytd():
    from rentals.utils import calculate_from_date
    from datetime import date
    assert calculate_from_date(date(2025, 6, 15), "YTD") == date(2025, 1, 1)
```
Run, confirm it crashes (current code raises on `months=`).

- [ ] **Step 2: Fix the bug**

Use `date(to_date.year, 1, 1)` for YTD. Re-run, confirm pass.

- [ ] **Step 3: Add the `case _:` default and clean dead code**

As described above.

- [ ] **Step 4: Run full suite, confirm green**

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "fix: YTD date calc crash; add default case to handle_element; remove dead code"
```

---

## Task 15: Postgres migration script

**Files:**
- Create: `property_rental/scripts/migrate_sqlite_to_postgres.py`

**Interfaces:**
- Produces: a runnable script that copies all rows from `db.sqlite3` to Postgres with verified row counts.

- [ ] **Step 1: Write the script**

```python
"""
One-shot migration: SQLite (db.sqlite3) -> Postgres.

Usage:
    DJANGO_SETTINGS_MODULE=property_rental.settings.prod python manage.py shell < scripts/migrate_sqlite_to_postgres.py

Requires: a populated db.sqlite3 next to manage.py, and DJANGO_DB_* env vars pointing at an EMPTY Postgres DB.
"""
import sqlite3
from django.conf import settings
from django.db import connection
from rentals.models import (User, Landlord, Property, Property_capital_structure,
                            Tenant, Lease_rent, Transaction, FX)

SQLITE_PATH = settings.BASE_DIR / "db.sqlite3"
MODELS = [User, Landlord, Property, Property_capital_structure, Tenant, Lease_rent, Transaction, FX]

def read_sqlite_rows(model):
    table = model._meta.db_table
    cols = [f.name for f in model._meta.fields]
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
    conn.close()
    return cols, [dict(r) for r in rows]

def main():
    # 1. Apply migrations to Postgres (empty DB)
    from django.core.management import call_command
    call_command("migrate", verbosity=1)

    summary = {}
    for model in MODELS:
        cols, rows = read_sqlite_rows(model)
        before = len(rows)
        # Bulk insert in batches of 500
        objs = [model(**{k: v for k, v in r.items() if k in cols}) for r in rows]
        for i in range(0, len(objs), 500):
            model.objects.using("default").bulk_create(objs[i:i+500])
        after = model.objects.using("default").count()
        summary[model.__name__] = (before, after)
        if before != after:
            raise SystemExit(f"MISMATCH {model.__name__}: sqlite={before} postgres={after}")

    print("Migration OK. Row counts:")
    for name, (b, a) in summary.items():
        print(f"  {name}: {b} -> {a}")
```

- [ ] **Step 2: Test against a copy**

Make a backup copy of `db.sqlite3`. Provision an empty Postgres DB. Run the script. Confirm the summary prints matching counts. Spot-check a few rows in the Postgres DB against SQLite.

- [ ] **Step 3: Commit**

```bash
git add scripts/migrate_sqlite_to_postgres.py
git commit -m "feat: add verified SQLite->Postgres migration script"
```

---

## Task 16: DRF serializers and permissions

**Files:**
- Create: `property_rental/rentals/api/__init__.py`, `serializers.py`, `permissions.py`
- Modify: `property_rental/property_rental/settings/base.py` — add `"rest_framework"` to `INSTALLED_APPS`.

**Interfaces:**
- Produces: `PropertySerializer`, `TenantSerializer`, `TransactionSerializer`, `FXSerializer`, `ChartDataResponseSerializer`; `IsOwnerOrReadOnly` permission.

- [ ] **Step 1: Add DRF to INSTALLED_APPS and configure default auth/permissions**

In `base.py`:
```python
INSTALLED_APPS += ["rest_framework"]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

- [ ] **Step 2: Write serializers**

`rentals/api/serializers.py` — one `ModelSerializer` per entity. For `Property`, `Tenant`, `Transaction`, expose all user-facing fields. For `ChartDataResponse`, a `Serializer` with `labels` (list), `datasets` (list of dicts), `currency` (char).

- [ ] **Step 3: Write the permission**

`rentals/api/permissions.py`:
```python
from rest_framework.permissions import BasePermission

class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return obj.owned_by.user == request.user
        return obj.owned_by.user == request.user
```

- [ ] **Step 4: Write a smoke test**

`test_api.py::test_serializer_validates_property` — instantiate `PropertySerializer` with valid data, assert `is_valid()`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add DRF serializers and IsOwnerOrReadOnly permission"
```

---

## Task 17: DRF ViewSets and `/api/v1/` routing

**Files:**
- Create: `property_rental/rentals/api/views.py`, `rentals/api/urls.py`
- Modify: `property_rental/rentals/urls.py` — `include("rentals.api.urls")` under `api/v1/`.

**Interfaces:**
- Produces: `PropertyViewSet`, `TenantViewSet`, `TransactionViewSet`, `FXViewSet`, `ChartDataView`; URL namespace `/api/v1/`.

- [ ] **Step 1: Write failing API test**

In `test_api.py`:
```python
def test_property_list_requires_auth(db, client):
    resp = client.get("/api/v1/properties/")
    assert resp.status_code in (401, 403)

def test_property_list_returns_only_own_properties(auth_client, sample_property):
    resp = auth_client.get("/api/v1/properties/")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert sample_property.id in ids
```

- [ ] **Step 2: Implement ViewSets**

`rentals/api/views.py` — `ModelViewSet` per entity. Override `get_queryset()` to filter by `owned_by__user=request.user`. Set `permission_classes = [IsOwnerOrReadOnly]`.

- [ ] **Step 3: Implement `ChartDataView`**

An `APIView` GET handler that parses `type, id, freq, start, end, currency` from query params, calls `services.charts.get_chart_data(...)`, validates ownership of the referenced entity, and returns the payload via `ChartDataResponseSerializer`.

- [ ] **Step 4: Wire URLs**

`rentals/api/urls.py`:
```python
from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import PropertyViewSet, TenantViewSet, TransactionViewSet, FXViewSet, ChartDataView

router = DefaultRouter()
router.register(r"properties", PropertyViewSet)
router.register(r"tenants", TenantViewSet)
router.register(r"transactions", TransactionViewSet)
router.register(r"fx", FXViewSet)
urlpatterns = router.urls + [path("chart-data/", ChartDataView.as_view())]
```
In `rentals/urls.py`: `path("api/v1/", include("rentals.api.urls"))`.

- [ ] **Step 5: Run tests**

`pytest rentals/tests/test_api.py -v`. All pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add /api/v1/ DRF endpoints with per-user querysets and chart-data view"
```

---

## Task 18: CDN SRI hashes on template CDN tags

**Files:**
- Modify: `property_rental/rentals/templates/rentals/layout.html` (Bootstrap + Icons), `index.html`, `properties.html`, `tenants.html` (Chart.js + datalabels).

- [ ] **Step 1: Compute SRI hashes for each pinned CDN URL**

For each CDN `<script src=...>` and `<link href=...>`, fetch the file, compute `sha384` base64, and add `integrity="sha384-..."` and `crossorigin="anonymous"`. Use a tool like `https://www.srihash.org/` or `curl | openssl dgst -sha384 -binary | openssl base64 -A`.

- [ ] **Step 2: Add the attributes to each tag**

Pin the CDN versions explicitly (e.g. `chart.js@4.4.1` not `@latest`) so SRI hashes remain valid.

- [ ] **Step 3: Smoke-test page loads**

`python manage.py runserver`; load each page in a browser; confirm no SRI violations in console.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "security: add SRI hashes and pin CDN versions"
```

---

## Task 19: Definition-of-done verification

This task runs the full Phase-1 verification checklist from the spec §5. No code changes unless a check fails.

- [ ] **Step 1: Security verification**

```bash
pytest rentals/tests/test_security.py -v
python manage.py check --deploy
```
Confirm: all security tests pass; `check --deploy` reports no `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` warnings.

- [ ] **Step 2: Service-layer line-count check**

```bash
wc -l property_rental/rentals/views.py
```
Confirm: under 800 lines (down from 1120, shed ≥300).

- [ ] **Step 3: FX cache benchmark**

`pytest rentals/tests/test_services.py::test_fx_graph_is_cached -v` — green.

- [ ] **Step 4: Postgres migration verification**

Run `scripts/migrate_sqlite_to_postgres.py` against a copy of the real DB; confirm row counts match.

- [ ] **Step 5: API characterization**

`pytest rentals/tests/test_api.py rentals/tests/test_charts_char.py -v` — green; `/api/v1/chart-data/` returns the same shape as the legacy `get_chart_data`.

- [ ] **Step 6: Full characterization suite on Postgres**

After migrating, run `pytest --cov=rentals` and confirm the full suite is green on Postgres, with the same golden values as on SQLite.

- [ ] **Step 7: Settings reorganization verification**

```bash
ls property_rental/property_rental/settings/
git log --all --diff-filter=D -- property_rental/property_rental/settings.py
```
Confirm: `base.py`, `dev.py`, `prod.py` exist; old `settings.py` is deleted; `.gitignore` no longer excludes it.

- [ ] **Step 8: Manual smoke test of existing template pages**

`python manage.py runserver`; walk through home / properties / tenants / transactions / FX pages; confirm identical behavior to before (no regressions).

- [ ] **Step 9: CI green**

Push to a branch, open a PR, confirm `.github/workflows/ci.yml` runs green on both Python 3.11 and 3.12.

- [ ] **Step 10: Commit + tag**

```bash
git commit --allow-empty -m "chore: Phase 1 Foundation modernization complete (verification passed)"
git tag phase-1-foundation
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task(s) | Covered? |
|---|---|---|
| §4.1 DELETE IDOR | Task 6 | ✅ |
| §4.1 missing auth (6 views) | Task 7 | ✅ |
| §4.1 `update_fx_view` scope | Task 7 | ✅ |
| §4.1 global as-of date | Task 8 | ✅ |
| §4.1 SECRET_KEY/DEBUG/ALLOWED_HOSTS | Task 1 | ✅ |
| §4.1 settings split | Task 1 | ✅ |
| §4.1 password validators | Task 1 | ✅ |
| §4.1 CDN SRI | Task 18 | ✅ |
| §4.2 FX schema wide→long (plan amendment) | Task 9 | ✅ |
| §4.2 services: fx | Task 10 | ✅ |
| §4.2 services: financials | Task 11 | ✅ |
| §4.2 services: charts + property_valuation fix | Task 12 | ✅ |
| §4.2 services: scheduler | Task 13 | ✅ |
| §4.2 bug: `calculate_from_date` | Task 14 | ✅ |
| §4.2 bug: `case _:` default | Task 14 | ✅ |
| §4.3 Postgres migration | Task 15 | ✅ |
| §4.4 DRF skeleton + chart-data endpoint | Tasks 16-17 | ✅ |
| §4.5 test scaffold | Tasks 1-5 | ✅ |
| §4.5 characterization tests | Tasks 3-5 | ✅ |
| §4.5 CI | Task 1 | ✅ |
| §5 verification | Task 19 | ✅ |

**2. Placeholder scan:** No "TBD"/"TODO"/"implement later". Task 10 Step 3 says "moved verbatim" — that's intentional (the body is in `models.py:521-591`, not reproduced here to avoid drift; the instruction is explicit and bounded). Task 15's script is fully written.

**3. Type consistency:** Service function signatures consistent across tasks:
- `services.fx.get_rate(from_currency, to_currency, as_of)` — defined Task 10, consumed Tasks 11, 17.
- `services.fx.convert(amount, from_currency, to_currency, as_of)` — defined Task 10, consumed Task 11.
- `services.financials.convert_transactions(qs, target_currency, as_of)` — defined Task 11, consumed Tasks 11, 12.
- `services.charts.get_chart_data(type, id, freq, start, end, currency, landlord)` — defined Task 12, consumed Task 17.
- `services.scheduler.debt(tenant, ...)`, `debt_advance_payment(tenant, ...)` — defined Task 13, consumed by `Tenant` model delegates.
All consistent.
