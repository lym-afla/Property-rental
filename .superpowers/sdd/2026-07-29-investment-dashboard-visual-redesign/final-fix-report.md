# Final fix report

Status: DONE

Implementation commit: `c058018` (`fix: harden investment dashboard release readiness`)

## Critical findings

1. **Negative expenses plotted above zero — resolved.**
   - Net cash flow now uses Recharts' signed stack geometry (`stackOffset="sign"`).
   - Unit coverage asserts the signed stack configuration and category patterns.
   - Windows/Chrome Playwright coverage inspects the actual SVG reference line and bar bounding boxes to prove income is above zero and expense marks extend below zero.

2. **Analytics caches not invalidated after source mutations — resolved.**
   - Transaction, FX, property valuation, property, tenant, lease-rent, and tenant-vacate mutations invalidate `queryKeys.analytics.all`.
   - Mutation tests cover analytics invalidation for the source API modules that already have mutation suites.

3. **React-owned financial semantics — resolved.**
   - Property detail P&L now uses the typed, property-scoped portfolio summary in the property's natural currency instead of duplicating transaction category taxonomy and arithmetic in React.
   - Tenant detail no longer sums mixed original-currency transactions. It presents server-owned rent/debt statistics and typed rent-performance analytics.
   - Tests assert the server values and query scope/effective date.

4. **Occupancy values silently clamped/falsified — resolved.**
   - The endpoint contract requires the exact capacity, occupied, vacant, and occupancy-rate series.
   - Point validation enforces non-negative integers, `occupied + vacant = capacity`, rate `0..100`, and a rate consistent with the counts.
   - The chart renders validated server values unchanged; invalid responses enter the existing query error path rather than being rewritten.

5. **Plotted series rely on color alone — resolved.**
   - Series styles now include stable dash patterns and marker shapes.
   - Revenue/expense lines use distinct dash patterns, yield scatters use distinct shapes, and cash-flow, valuation, and rent-performance bars use distinct SVG patterns applied to the marks themselves.
   - Component tests inspect the actual Recharts mark props.

## Important findings

1. **Comparison control is a no-op — resolved by removal.**
   - Comparison was removed from dashboard filter state, parsing, serialization, UI, defaults, and requests until a server contract exists.
   - Tests verify copied legacy query keys do not restore a control or reach analytics requests.

2. **Missing FX paths return 500 — resolved.**
   - FX conversion now raises a dedicated `MissingFXRate` error for unavailable graph nodes/paths/rates.
   - Portfolio analytics translate it to deliberate HTTP 422 responses with `code: "missing_fx"` and a detail message.
   - API tests cover summary, cash flow, expenses, contribution, yields, and rental-income exposure.

3. **Unbounded ranges and year-9999 crash — resolved.**
   - Analytics filters reject requests exceeding 600 output points for the requested grain.
   - Calendar iteration safely terminates at `date.max` without constructing year 10000.
   - README documents the point limit; tests cover both boundaries.

4. **Dashboard sections all render/request everything — resolved.**
   - Overview, Income & Costs, Portfolio, and Risk render section-specific components with colocated hooks.
   - A request-count regression proves Overview requests cash flow only (plus the global summary), with zero irrelevant endpoint requests.

5. **Populated visual baselines contain error/empty charts — resolved.**
   - Visual fixtures now provide contract-valid, multi-period cash-flow aggregates, expenses, exposure, and occupancy invariants.
   - The spec asserts intended Overview charts and no alert state before snapshotting, verifies exact-value table mode, and refreshes all six desktop/tablet/mobile baselines.

6. **Runtime contracts omit chart-required series — resolved.**
   - Cash-flow contracts use endpoint-specific kind enums, require total income, total expenses, net income, and cumulative net income series, and require numeric aggregate values per point.
   - Expense-driver and occupancy responses have endpoint-specific series contracts and strict point validation.
   - Contract tests reject missing cash aggregates and inconsistent occupancy payloads.

7. **Tenant analytics ignores effective date — resolved.**
   - Tenant rent-performance uses the authenticated user's effective date, or omits the end when the user has no configured date.
   - Page coverage asserts the request end date.

8. **Partial-period drill bounds mismatch bars — resolved.**
   - Cash-flow and expense response points clamp their first/last public period bounds to the requested range while retaining calendar buckets for aggregation.
   - Tests cover partial monthly and quarterly ranges.

9. **390px navigation compressed/not touch-sized — resolved.**
   - Desktop navigation is hidden below `md`; mobile uses a five-destination fixed bottom navigation with 44px minimum targets and content clearance.
   - Playwright at 390x844 asserts five visible destinations, every target at least 44x44, and no horizontal overflow.

10. **Visual snapshots share incompatible platform/browser baselines — resolved.**
    - Exact-pixel visual tests run only on Windows Chrome.
    - The E2E CI job uses `windows-latest` and `PW_CHANNEL=chrome`, matching the documented local generation command.

## Minor findings

- Removed the trailing blank line from `property_rental/rentals/api/views.py`; `git diff --check` passes.
- Updated README frontend technology, analytics routes/locations, point-limit behavior, and pinned visual-test workflow.

## Verification

- `python -m pytest -q` from `property_rental/`: **202 passed**.
- `python manage.py check` from `property_rental/`: **no issues**.
- `npm run lint` from `frontend/`: **exit 0**.
- `npm test` from `frontend/`: **36 files, 160 passed**.
- `npm run build` from `frontend/`: **passed**.
- `$env:PW_CHANNEL='chrome'; npm run test:e2e -- --workers=1` from `frontend/`: **26 passed, 4 intentional project-specific skips** across desktop, tablet, and mobile.
- `git diff --check`: **passed**.

## Remaining concerns

- Recharts logs transient `ResponsiveContainer` width/height warnings during initial E2E layout. Final chart geometry, tables, snapshots, and all assertions pass at all three viewports.
- Lint reports existing Fast Refresh and unused-expression warnings but no errors. The new pattern helper was placed in the non-component theme module so it adds no Fast Refresh warning.
- No final-review finding was classified as a false positive; all Critical, Important, and Minor findings above were addressed.
