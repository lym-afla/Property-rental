# Wealth loans implementation plan

**Goal:** Preserve Rent loan/payment history for correct Rent reports and Wealth v1.1 imports.
**Architecture:** Extend existing models and canonical semantics; scoped loan API and atomic payment split; property UI; read-only export.
**Tech stack:** Django, DRF, React, TypeScript, existing test tools.
**Spec:** docs/superpowers/specs/2026-11-14-wealth-loans-design.md

## Constraints and review focus
- Local branch only. No production, pushes, merges or changes outside Rent.
- Preserve existing signs; new loan payments positive, interest expense, principal balance sheet.
- Prevent cross-owner/property/currency loan references, including partial updates.
- Test historical migration, nullable and same-date observations, multiple loans, stable hashes and read-only queries.
- Use v1.1 exact fields and validate with Wealth parser when available.

## Tasks
- [x] Backend: add failing model/API/report tests; implement Loan, timestamps, migrations, semantics, atomic split and reconciliation; run targeted tests.
- [x] Frontend: add loan management and payment split UI, loan fields in transaction and valuation forms; verify entry, errors, reconciliation and build.
- [x] Export: add failing command tests; implement subject-scoped v1.1 export with real timestamps/content hashes; document read-only production role and history usage.
- [x] Integrate: run complete backend/frontend checks and parser validation on synthetic data, review diff and migration safety, prepare version bump/changelog, commit locally and report limitations.

## Verification

- Python 3.11 (matches Docker and CI): 551 passed, 1 PostgreSQL-only test skipped.
- Frontend after rebasing onto Rent 2.2.0: 296 passed; production build passed. Lint exited successfully with two existing dependency warnings in TransactionsPage.
- Existing transaction browser flow passed on desktop, tablet and mobile (3 tests); the existing Select controlled/uncontrolled warning remains.
- Django system checks, migration drift check and whitespace checks passed.
- Synthetic export accepted by Wealth’s current local v1.1 parser. Local main/origin/main lack v1.1, so repeat after merge there.
- Actual database migrations were not run. No real loans were created or lender values changed.
- Schema migration 0029 adds loans/references/timestamps; data migration 0030 creates placeholder loans and reports property/loan IDs.

The first suite runs used the existing environment’s Python 3.14. Django 4.2 fails there with Context.__copy__ errors. A separate Python 3.11 environment resolved those failures without application changes. Affected tests: test_health::test_readiness_checks_the_default_database_and_hides_failures; test_oidc_authorization::test_explicit_public_routes_are_exempt[/static/app.js]; test_oidc_sessions::test_oidc_login_registers_final_rotated_django_session, test_relogin_replaces_same_session_key_association, test_local_password_login_does_not_create_oidc_session, test_oidc_session_requires_identity_and_nonempty_sid (three cases); test_internal_backchannel_transport::test_confusable_hosts_never_receive_the_internal_http_bypass (three cases). Feature-related valuation/import failures were corrected and pass in the final suite.

Final review corrected blank debt being interpreted as payoff, unlinked zero payoff reconciliation, principal missing from cash charts, and cash accumulation using operating profit. Blank balances now remain unknown; explicit zero records payoff. Existing tests that specified blank-as-zero were intentionally revised to enforce independent observation semantics.

## Release base correction

Fetched origin and tags, then rebased only the loan feature onto `40fcf49` (current `origin/main`, released as 2.2.0). Resolved the changelog and transaction form/test conflicts by retaining native currency defaults, former-tenant selection, saved accounting periods and all existing tests alongside loan entry. Added a combined loan/property-switch regression test. Version 2.3.0 matches across backend, frontend, locks and changelog, with the 2.2.0 changelog preserved. Fast-forwarded local main to origin/main. Kept a local pre-rebase backup branch; no push, merge or production action.
