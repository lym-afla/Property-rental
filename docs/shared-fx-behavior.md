# Shared FX behavior in Rent

`FX_BACKEND=legacy` remains the default and preserves the existing financial and
HTTP contracts. Mirror is an explicit opt-in. Business records, native amounts,
lease dates, grace windows, transaction classifications and monetary display
rounding are unchanged. Mirror does deliberately change the following derived
financial behavior; these are not all explained by a different provider rate.

| Named cause | Code location | Difference and reason |
| --- | --- | --- |
| `rent_total_face_value` | `rentals/models.py::Tenant.rent_total` | Legacy sums payments at face value when the requested currency is omitted or equals the property's currency, even if a payment is foreign. Mirror converts each dated payment into the property's/requested currency. Both tenant-linked and unassigned property rent payments included by the rent-total date window can change. Summing different units would misstate received rent and debt. |
| `scheduler_rent_denomination` | `rentals/services/scheduler.py::debt` | Legacy treats a lease rent amount as property currency. Mirror converts the effective lease rent from its recorded currency at each contractual due date. Both standard and advance methods retain their original due dates and grace windows. |
| `scheduler_rent_selection` | `rentals/services/scheduler.py::debt`; `rentals/models.py::Tenant.lease_rent` | With duplicate effective dates, the mirror scheduler selects the highest primary key to make the latest recorded rent deterministic. Legacy orders by date alone, leaving tie selection database-dependent. Thus even two same-currency rows can select a different contractual amount without an FX change. Export attributes this cause only when another rent row shares the tenant/effective date. |
| `native_stats_and_pnl` | `rentals/api/views.py::PropertyViewSet.with_stats`; `rentals/services/financials.py::pnl_calc` | Legacy native presentation sums foreign transaction face values. Mirror converts them into the property/report currency. Tenant native stats inherit the `rent_total_face_value` and scheduler changes. No transaction amounts are rewritten. |
| `identity_requires_coverage` | `rentals/services/fx.py::convert`; `rentals/services/fx_mirror.py::get_rate` | Legacy identity conversion needs no reference data. Mirror requires dated applicability and an anchor even for a multiplier of one. Unsupported, before-coverage and unsynced dates cannot masquerade as covered. |
| `typed_missing_tenant_fx` | `rentals/analytics/tenant.py::_converted`, `tenant_rent_performance`; `rentals/api/analytics_views.py::_PortfolioAnalyticsView`; `rentals/api/views.py::_consistent_fx_report` | Tenant performance returns typed missing-FX issues, null expected/received values for the affected side, null variance and null cumulative arrears from the first gap onward; missing opening history nulls the opening balance and every later cumulative balance. Valid periods remain visible. The UI's existing incomplete-data states render these responses. Other aggregate reports return explicit HTTP 422 `missing_fx` rather than a partial total. |
| `provisional_completed_day` | `rentals/services/fx_mirror.py::get_rate`; report wrappers above | Dates after the latest completed snapshot through business today may use that snapshot only within the 14-day freshness ceiling. Results retain the effective snapshot date, are labeled provisional and are not cacheable. Future dates fail. Legacy does not supply this contract. |
| `canonical_reference_policy` | `rentals/services/fx.py::get_rate`, `PreloadedConverter`; `rentals/services/fx_mirror.py::get_rate` | One dated anchor ratio replaces shortest-path selection and independently dated edges. Mirror does not fall back to local/manual legacy observations, and enforces initial-v1 applicability, explicit fixed pegs and freshness. It uses one published snapshot per date; observation dates remain distinct. |
| `decimal_precision` | `rentals/services/fx.py::convert`, `PreloadedConverter`; `rentals/services/fx_mirror.py::get_rate` | Mirror isolates 38 significant digits with ROUND_HALF_UP, and quantizes multipliers to 18 places. Legacy uses its stored decimal scale and ambient arithmetic. Final domain rounding is unchanged. |

Missing FX never blocks a valid native transaction save/import. Mirror import
preserves business facts but skips legacy reference rows
(`rentals/management/commands/import_sqlite.py`). This is reference ownership,
not a change to the business transaction.

`export_fx_comparison` schema 2 contains stable private primary keys, original
business hashes and dated currency evidence, source commit/image digest supplied
by the operator (null when absent), release ID/sequence/history epoch, explicit
report horizon, and allowlisted backend settings. Only `header.generated_at`
varies for identical inputs. Output files are mode 0600. Never commit exports.

```sh
python manage.py export_fx_comparison --output /private/comparison.json \
  --source-commit "$RENT_SOURCE_COMMIT" --image-digest "$RENT_IMAGE_DIGEST" \
  --as-of 2026-11-05 --report-start 2026-01-01 --report-currency USD
```

`FX_EXPORT_SOURCE_COMMIT` and `FX_EXPORT_IMAGE_DIGEST` are equivalent argument
defaults. Missing provenance is deliberately retained, not inferred from checkout
HEAD or a fabricated digest. The consumer blocks it. These are supplied claims;
operators must independently verify the deployment attestation.

The command calls live tenant rent/debt (standard and advance), native property
stats, native and converted property P&L, portfolio transaction totals, tenant
rent performance, and annual P&L analytics paths. The `report_coverage` inventory
lists each family/entity/currency. Required `report_scope` records the original property-to-owner and tenant-to-property relationships plus dated transaction scope and live category labels. It also includes tenant lease start/end/payday, deposits (tenant/date/currency), capital (property/date), and lease rents (tenant/effective date/currency). Its IDs must exactly cover the business inventory. The consumer derives every required owner/entity/currency, fixed metric, monthly tenant point and annual P&L year from these facts and the horizon; the metric manifest cannot waive them. Independently derived raw and contractual due-date rows must each contain exactly USD/EUR/GBP/RUB target conversions, with original inventory hashes; omissions, extras, duplicates and contradictions block. Due dates use the tenant analytics month-end payday clamp and lease boundaries, selecting the latest effective rent by date then numeric primary key. The report start bounds tenant performance and
selected-period analytics; debt includes lease history, P&L includes all-time and
YTD, annual P&L includes historical annual columns. Native property stats retain
the live endpoint's full-calendar-year YTD window. Independently review these
scopes against the operational reports, including future-dated transactions.
Portfolio valuation completeness remains a separate capital/inventory review;
portfolio receipts here measure revenue, costs and net income.

Each numeric metric is evaluated in this fixed order on one business snapshot:
legacy resolver/behavior; mirror resolver with legacy behavior; then enable
`rent_total_face_value`, `scheduler_rent_denomination`,
`scheduler_rent_selection`, and `native_stats_and_pnl` one at a time. Adjacent
stage subtraction supplies each cause's signed amount. Native rent/debt/stats/P&L reference-only stages must remain equal: with all behavior flags off, those live paths sum face values and never call the resolver. Successful numeric rates and reports require an explicit null error field; missing and all non-null values, including falsy values, block. This quantifies mixed
payments and tied effective rents using the real algorithms; interaction effects
belong to the later stage, so ordering is part of the contract. The final stage
is the live mirror behavior. Resolver changes are named
`canonical_reference_policy` in reports; exact row multipliers distinguish that
policy from 18-place `decimal_precision`, and canonical rate changes still need
independent dated source receipts. Applicability labels alone cannot waive a
difference. Missing rates/report values and calculation failures use typed codes,
never private exception messages, and block cutover. Unproven residuals must be
reported as unexplained, never absorbed into a behavior label.

`ContextVar` selection isolates concurrent requests and nested calculations.
Production code never changes global `FX_BACKEND`. PostgreSQL exports require
a top-level repeatable-read/read-only transaction; nested transactions fail
explicitly. SQLite uses its transaction snapshot. An SQL guard rejects writes
rather than relying on rollback. Both business inventory and release are checked
within the snapshot. No reference sync or business writes occur during export.

LifeOS verifies stage order, arithmetic, allowed causes per report family,
required entity coverage, provenance and release pins. Its stdout includes only
aggregate count, changed count, signed/absolute/max movement, grouped by family,
currency and cause. Metrics overlap (components, totals, YTD and all-time), so
these sums measure report movement, not net portfolio economic impact. Review
private per-metric receipts for each of the four deliberate-change sign-offs.

## Browsing contract and compatibility

In legacy mode, `/api/v1/fx/` still returns the original array and numeric-ID
detail returns the original serialized legacy row. In mirror mode, the same
authenticated route returns a paginated envelope:

```text
GET /api/v1/fx/?base=EUR&quote=RUB&start=2026-01-01&end=2026-01-31&page_size=10
{backend, release_id, status, count, first, next, results}
```

The selected pair is bounded to the nine initial-policy currencies, the date
range to 31 inclusive days, and page size to 1–31 (default 10). The default pair
is USD/EUR and the default range ends on the latest completed mirror date and
starts 30 days earlier. Rows descend by valuation date. Missing dates/rates are
explicit rows with null rate and a typed error; they are never zero. Empty
mirrors distinguish `unsynced` (no release) from `empty` (no available anchors).

Each row exposes direction, valuation/effective dates, decimal-string multiplier,
direct/derived/identity method, canonical path, policy source labels, oldest
endpoint-anchor observation date, carried/provisional flags and release/snapshot
IDs. A path label does not claim the service was contacted. Initial-v1 topology
is already enforced by mirror sync; unknown policies fail there. Observation
dates are conservative anchor metadata, not invented edge-specific timestamps.
The page labels them "Oldest anchor observation"; full snapshot provenance is
available in details.

The first read locks the same sync-state row as sync while materializing at most
31 rows for one pair. `first` and `next` carry this immutable view in compressed
signed cursors, each capped at 6,000 characters and valid for 24 hours. Every page,
including page one after backward navigation or cache eviction, reads that view
without HTTP or current anchors, so a promotion or outage cannot substitute
new rows under the previous release label. Follow either link without additional
filters. Malformed, tampered, oversized, expired or filter-combined cursors fail
with HTTP 400. Refresh range restarts browsing at the current mirror release.
Mirror browsing does not repin on window focus or reconnect. Explicit refresh,
retry after expiry and filter changes create a fresh browsing-session key, so
they request the current mirror even when an earlier unpinned query is cached as
fresh. This avoids a history table, shared cache infrastructure and worker-local
state while preserving the initial page independently of React Query's cache.

`GET /api/v1/fx/details/?token=<row details_token>` resolves the selected row
through the existing service batch client using its signed release and query.
It verifies the service release, snapshot and exact multiplier against the
browsed row. A service outage or mismatch returns HTTP 503
`fx_details_unavailable`; the local table remains readable. Snapshot sources and
observations are labeled as snapshot evidence because the service supplies the
whole snapshot, which can include currencies outside the selected pair. Numeric
legacy detail IDs are unavailable in mirror mode. Inspection creates no anchors,
edges or legacy rows.

The only frontend array consumer was `FXPage` through `useFX`; the repository-wide
caller audit found no others. The hook now accepts the array/envelope union, and
the page dispatches arrays to the retained legacy summary (including as-of and
inverse display). All nine strict analytics response schemas also accept optional,
strictly validated mirror metadata; unknown response fields still fail validation.

This is an opt-in extension under `FX_BACKEND=mirror`, introduced in the same
unmerged feature as the mirror backend. Existing default/legacy API clients and
data remain compatible. The branch therefore retains version **2.3.0**, rather
than introducing a major version for a new mode that has not been cut over.
Clients opting into mirror must consume the documented envelope. Changelog
entries describe both mirror calculations and browsing under that version.

## Read-only boundary audit

- `rentals/api/views.py::FXViewSet` stays `ReadOnlyModelViewSet` with authenticated
  reads. POST/PATCH/DELETE and import attempts are rejected; mirror numeric IDs
  cannot expose legacy evidence as shared reference data.
- `rentals/urls.py` and `rentals/views.py` retain only the SPA shell and API include;
  retired `/update-fx/` and `/handling/` POST requests return 405 and cannot write.
- `rentals/admin.py` registers neither FX, FXAnchor nor FXSyncState. There is no
  admin add/change/delete route for reference data.
- `rentals/management/commands/import_sqlite.py` skips FX rows in mirror mode while
  preserving native records. Existing Task 6 tests exercise both backends.
- `sync_fx` remains the sole writer of shared anchors and state. It imports
  published immutable snapshots; browsing never invokes it or a provider.
- Operator-only `refresh_fx` retains its ability to write the legacy evidence
  table for rollback and the governing migration's legacy-timer soak period.
  It never changes mirror anchors/state and has no HTTP/admin/import mutation
  route. Timer retirement and production cutover belong to Task 10.
