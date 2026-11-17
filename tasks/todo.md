# Valuation mortgage labels

- [x] Confirm historical rows read the parent lender; add regression coverage for dated products, loan isolation, missing history and fetch/retry states.
- [x] Fetch products for the property and resolve each linked loan/date with inclusive product bounds.
- [ ] Verify tests/build, bump 2.5.1, review and release through Life OS.
- [ ] Verify deployed labels and financial preservation; record acceptance.

Use existing owner-scoped product API and query invalidation. Keep the loan accounting identity and all business rows unchanged. Account reference remains in Edit loan; never substitute it for historical product identity.

Verification: 308 frontend tests, build/typecheck, version checks and independent review passed. Lint retains two existing TransactionsPage warnings. No backend or data changes.
