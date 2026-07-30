# Final fix wave 2 report

## 1. Status

DONE

## 2. Finding-by-finding resolution

### Cash-flow category visual identity collision

- Extended the stable series-token set from three identities to nine, matching all supported backend transaction categories.
- Added a distinct non-color SVG texture for every additional category token while preserving the established primary/secondary visual baseline.
- Regression evidence: `NetCashFlowChart.test.tsx` renders all nine supported income/expense categories and asserts nine distinct mark fills.

### Year-9999 month/quarter bucketing

- `_next_period_start` now returns `None` only when the requested grain's actual successor would exceed `date.max`.
- `_calendar_periods` therefore preserves every valid month, quarter, or year bucket and never constructs year 10000.
- Regression evidence: monthly `9999-01-01..9999-02-28` yields January and February; quarterly `9999-01-01..9999-06-30` yields Q1 and Q2; the existing `9999-12-31` terminal-boundary test remains green.

### Saved All-history + monthly dashboard regression

- Dashboard defaults normalize the supported saved `All` + monthly combination to bounded yearly analytics requests before any endpoint is called.
- Other saved grains and explicit URL selections remain unchanged.
- Regression evidence: `HomePage.test.tsx` proves both summary and cash-flow overview requests use `start=1900-01-01&grain=year` for a saved All/monthly profile.
- Resource protection remains intact: the existing backend regression still rejects an arbitrary 2000–2050 monthly range over the 600-bucket cap.

## 3. RED command/output summary

- `npm test -- --run src/features/dashboard/charts/NetCashFlowChart.test.tsx src/pages/HomePage.test.tsx`
  - Cash-flow identity regression failed: expected 9 distinct fills, received 3.
  - All-history regression failed: expected `grain=year`, received `grain=month` for both requests.
  - One unrelated HomePage test initially inherited deliberately mutated session state after the failing assertion; `afterEach` isolation removed that test-only fallout before production changes.
- `python -m pytest -q rentals/tests/test_analytics_cash_flow.py -k "date_max or requested_grain"`
  - 2 failed, 1 passed: monthly and quarterly cases each returned one collapsed bucket instead of two.

## 4. Verification commands/output summary

### Focused

- `npm test -- --run src/features/dashboard/charts/NetCashFlowChart.test.tsx src/pages/HomePage.test.tsx`: 2 files, 9 tests passed.
- `python -m pytest -q rentals/tests/test_analytics_cash_flow.py rentals/tests/test_analytics_contracts.py`: 28 passed.
- `$env:PW_CHANNEL='chrome'; npm run test:e2e -- e2e/investment-dashboard-visual.spec.ts --workers=1`: 3 passed after preserving the established primary visual texture.

### Full

- `python -m pytest -q`: 204 passed.
- `python manage.py check`: no issues (0 silenced).
- `npm run lint`: exit 0; existing warnings only.
- `npm test`: 36 files, 162 tests passed.
- `npm run build`: passed (`tsc -b && vite build`).
- `$env:PW_CHANNEL='chrome'; npm run test:e2e -- --workers=1`: 26 passed, 4 intentional viewport-specific skips.
- `git diff --check`: passed.

## 5. Commit hashes

- `e4708a76ccf85ef0dd3745118e02a8b5c42b72fd` — `fix: resolve final dashboard release blockers`

## 6. Concerns

- Recharts continues to emit transient initial `ResponsiveContainer` width/height warnings in Playwright; final geometry, visual baselines, and all assertions pass.
- Lint continues to report the repository's existing Fast Refresh and unused-expression warnings, with no errors.
- The saved All/monthly preference is intentionally displayed and requested at yearly grain to stay within the backend allocation cap; users can still choose a different bounded range and finer grain explicitly.
