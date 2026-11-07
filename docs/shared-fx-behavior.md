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

`export_fx_comparison` exports this cause catalog as `behavioral_differences`.
Each row's `applicable_behavioral_causes` identifies the affected calculation
paths, including mixed-currency rent and native P&L; applicability is not a claim
that an aggregate changed numerically. `multiplier_difference_cause` separately
identifies `reference_coverage` when only one resolver has a rate,
`decimal_precision` when the difference disappears at the declared 18-place
ROUND_HALF_UP precision, or `canonical_reference_policy` for remaining numeric
differences. Equal numbers with different trailing zeros have no delta cause. A
multiplier comparison alone cannot quantify face-value/scheduler changes.
Business hashes and original currency/date fields remain in the export so those
changes can be investigated without attributing every delta to rate source.

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
