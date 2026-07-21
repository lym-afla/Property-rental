# Phase 4 Architecture Debt Cleanup — Design Spec

**Date:** 2026-07-21
**Status:** Approved (pending user review of written spec)
**Predecessors:** Phase 1 (`phase-1-foundation`), Plan A (`spa-foundation`), Plan B1 (`entity-backend-infra`), Plan B2 (`entity-pages-legacy`), Plan C (`charting-dashboard`)

---

## 1. Context

The full modernization (Phase 1 → Plan C) is complete and merged to `main`. The app is a React SPA consuming a DRF backend with zero legacy template code, 8 Recharts charts, 197 tests green. Phase 4 addresses the architecture-debt items explicitly deferred throughout the prior phases — all backend, no frontend changes.

## 2. Goals

1. Unify `debt`/`debt_advance_payment` into one parameterized function, eliminating the ~90% duplication and the local-var-shadows-function-name footgun.
2. Normalize `pnl_calc`'s mixed numeric types to all-`float`, updating the pinned golden values.
3. Harden the FX graph cache: switch to Django's cache framework, add `post_save`/`post_delete` signal-based invalidation (catches bulk ops), use `cache.get_or_set`.
4. Replace 9 stray `print()` calls with `logging` in `services/fx.py` and `utils.py`.
5. Add prod cookie-security settings (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS, SSL redirect, `CSRF_TRUSTED_ORIGINS`).
6. Tighten `UserSerializer` writable surface — mark identity/role fields read-only so `PATCH /auth/me/` can't change `is_landlord`/`is_tenant`.

## 3. Non-Goals

- No frontend changes.
- No new features.
- No database schema changes.
- No Phase 5+ scope (further feature development).

## 4. Design

### 4.1 Debt function unification

**Current state:** `scheduler.py` has two functions:
- `debt(tenant, as_of_date=None)` (~line 53) — standard method: month counted as due from day 1, 3-day grace period.
- `debt_advance_payment(tenant, as_of_date=None)` (~line 146) — advance method: only completed months count; current month due if >7 days past due date.

They share ~90% identical code (the month-iteration loop). The difference is two threshold values:
- Grace period days: 3 (standard) vs 7 (advance).
- Whether the current month is "due" immediately or only after the threshold.

**The unification:**

```python
def debt(tenant, as_of_date=None, method='standard'):
    """
    Unified debt calculation for a tenant.

    method='standard' — month is due from day 1; 3-day grace period.
    method='advance'  — only completed months are due; current month due
                        only if >7 days past the due date.

    The month-iteration logic is identical; only the threshold and
    the current-month-is-due condition differ.
    """
    thresholds = {
        'standard': {'grace_days': 3, 'current_month_due': True},
        'advance': {'grace_days': 7, 'current_month_due': False},
    }
    config = thresholds.get(method, thresholds['standard'])
    # ... unified loop using config['grace_days'] and config['current_month_due'] ...
```

The `Tenant.debt()` model delegate calls `services.scheduler.debt(self, as_of_date, method='standard')`. The `Tenant.debt_advance_payment()` delegate calls `services.scheduler.debt(self, as_of_date, method='advance')`.

**Local-variable rename:** rename the inner `debt = total_rent_paid - total_rent_due` to `balance` or `net_debt` to avoid shadowing the function name.

**Testing:** the existing char tests (`test_tenant_debt_arrears_scenario` and `test_tenant_debt_advance_payment_scenario`) pin both at `-2000.00`. After unification, both must still produce `-2000.00` (they converge on the test scenario). Add a test with a scenario where the two methods diverge (e.g., a tenant whose current month is within the grace period — standard counts it, advance doesn't).

### 4.2 pnl_calc mixed-types normalization

**Current state:** `pnl_calc` returns `(expenses, rent_ytd, rent_all_time, unique_categories)` where:
- Per-category values in `expenses`: `float` (via `round(float(cf_ytd), digits)`).
- `expenses['total']` sub-dict: `Decimal` (accumulated raw, pre-cast).
- `rent_ytd`/`rent_all_time`: bare `Decimal` or `int 0`.

**The fix:** normalize everything to `float`. Cast `total` sub-dict and rent fields through `float()` before returning. The `digits` rounding is applied uniformly.

**Testing:** `test_pnl_calc_portfolio` pins the mixed-types shape. Update the golden values — same numbers, all `float`:
- `Decimal("500")` → `500.0`
- `Decimal("200")` → `200.0`
- etc.

### 4.3 FX cache hardening

**Current state:** `services/fx.py` uses a module-level dict `_graph_cache = {"graph": None, "as_of": None}`. Invalidation happens via `FX.save()`/`FX.delete()` overrides (which miss bulk operations). Single-slot cache thrashes on alternating `as_of` dates.

**The fix:**

1. **Switch to Django's cache framework:**
   ```python
   from django.core.cache import cache

   CACHE_KEY_PREFIX = 'fx_graph:'
   CACHE_TIMEOUT = 3600  # 1 hour

   def _get_graph(as_of):
       key = f'{CACHE_KEY_PREFIX}{as_of.isoformat()}'
       graph = cache.get(key)
       if graph is None:
           graph = build_graph(as_of)
           cache.set(key, graph, CACHE_TIMEOUT)
       return graph
   ```

2. **Signal-based invalidation:** replace the `FX.save()`/`FX.delete()` overrides with `post_save`/`post_delete` signals in a `signals.py` module (or inline in `models.py` via `@receiver`):
   ```python
   from django.db.models.signals import post_save, post_delete
   from django.dispatch import receiver

   @receiver([post_save, post_delete], sender=FX)
   def invalidate_fx_cache(sender, **kwargs):
       from django.core.cache import cache
       # Delete all fx_graph:* keys (cache doesn't support pattern delete in LocMem;
       # for now, use a version counter)
       cache.incr_or_set('fx_graph_version', default=1)
   ```
   Or simpler: use `cache.clear()` for LocMem (acceptable for a personal app). The version-counter approach is Redis-ready.

3. **Remove the `FX.save()`/`FX.delete()` overrides** from `models.py` (the signals handle invalidation).

**Testing:** extend the FX cache test to verify:
- Signal-based invalidation fires on `FX.objects.create()` (bulk path that bypasses `save`).
- Cache survives across calls within the same `as_of`.
- Different `as_of` values get separate cache entries.

### 4.4 Replace print() with logging

Replace 9 `print()` calls in `services/fx.py` (6 calls) and `utils.py` (3 calls) with `logging.getLogger(__name__)`:
- Progress messages → `logger.info(...)`.
- Error messages → `logger.warning(...)` or `logger.error(...)`.

Add a basic `LOGGING` config to `settings/base.py`:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
```

### 4.5 Prod cookie-security settings

Add to `property_rental/property_rental/settings/prod.py`:
```python
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o
]
```

**Testing:** `check --deploy` should report fewer warnings (W004, W008, W012, W016 addressed).

### 4.6 UserSerializer writable surface

In `property_rental/rentals/api/serializers.py`, add `read_only_fields` to `UserSerializer`:
```python
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [...]
        read_only_fields = ['id', 'username', 'is_landlord', 'is_tenant']
```

**Testing:** add `test_patch_me_cannot_change_role` asserting `PATCH /auth/me/` with `{"is_landlord": false}` does not change the flag.

## 5. Verification (definition of done)

1. `scheduler.py` has ONE `debt` function (parameterized), not two. The model delegates call it with the right `method`.
2. `pnl_calc` returns all-`float` values. Char test golden values updated.
3. FX cache uses Django's cache framework with signal-based invalidation. Bulk ops invalidate.
4. Zero `print()` calls in `services/` or `utils/`. `LOGGING` config in `base.py`.
5. `prod.py` has all 7 cookie-security settings.
6. `UserSerializer` marks `id`/`username`/`is_landlord`/`is_tenant` as read-only.
7. All suites pass: 112 backend (with updated golden values) + 85 frontend.
8. `check --deploy` reports 4+ fewer warnings vs before.

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Debt unification changes output for edge cases | Add a diverging-scenario test; existing char tests catch regressions |
| pnl_calc type change breaks SPA consumers | The SPA already handles both float and Decimal (JS coerces); update TS types to `number` |
| FX cache switch introduces stale-data window | TTL is 1 hour; signal-based invalidation covers writes; acceptable for personal app |
| Cookie settings break dev | Settings go in `prod.py` only; `dev.py` is unaffected |

## 7. Open questions

None blocking.
