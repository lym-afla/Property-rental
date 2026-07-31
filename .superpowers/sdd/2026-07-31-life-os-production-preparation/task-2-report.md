# Task 2 Report: Durable OIDC Identity and Claim Binding

## What changed

- Added `OIDCIdentity`, a one-to-one durable binding from a local user to an exact OIDC `(issuer, subject)` pair, with database uniqueness and application-level immutability.
- Added `RentalOIDCAuthenticationBackend`. The upstream backend continues to perform protocol claim validation; the subclass enforces exact issuer, subject presence, configured group-claim shape, viewer membership, durable lookup, and non-email-based provisioning.
- New OIDC users receive a subject-derived non-profile username, mutable email profile data, and an unusable password. Existing local users are never merged by email.
- Added `mark_session_authorized`, which writes only sorted authorized groups and an ISO UTC timestamp, and only for the viewer group. Provider tokens remain disabled in session storage.
- Wired the custom backend, OIDC app/routes, scopes, RS256/JWKS, PKCE, redirect hosts, and production/development backend separation. Preserved environment-driven production callback routing.

## TDD RED/GREEN evidence

- RED: initial focused run failed during collection because `OIDCIdentity` did not exist.
- GREEN iteration: after minimal model/backend/settings implementation, 8 OIDC tests passed.
- RED: added immutable-binding regression test; it failed because changing `subject` was accepted (`DID NOT RAISE ValidationError`).
- GREEN: added the immutable save guard; final focused/regression suite passed 18 tests.

## Tests run/results

- `uv run pytest property_rental/rentals/tests/test_oidc.py property_rental/rentals/tests/test_production_settings.py -q` — 18 passed.
- `uv run python property_rental/manage.py makemigrations --check --dry-run` — no changes detected.
- `uv run python property_rental/manage.py migrate` — no migrations to apply on final run; `0023_oidc_identity` applied successfully on the preceding run.
- `git diff --check` — clean.

## Files changed

- `property_rental/rentals/models.py`
- `property_rental/rentals/migrations/0023_oidc_identity.py`
- `property_rental/rentals/oidc.py`
- `property_rental/rentals/tests/test_oidc.py`
- `property_rental/property_rental/settings/base.py`
- `property_rental/property_rental/settings/dev.py`
- `property_rental/property_rental/settings/prod.py`
- `property_rental/property_rental/urls.py`
- `property_rental/property_rental/production_urls.py`

## Self-review findings

- Durable lookup never consults username or email.
- The subclass delegates the base `verify_claims` call and does not implement token signature, audience, nonce, or cryptography handling.
- Issuer comparison is exact; trailing-slash trimming is used only to construct endpoint URLs, not to alter identity semantics.
- Database constraints cover both one identity per user and one user per issuer/subject pair.
- Production has no password backend; development retains only the local model backend.

## Concerns

- Django emits the pre-existing `staticfiles.W004` warning because `property_rental/rentals/static` is absent in this worktree. It does not affect OIDC behavior.

## Fix round 1: callback integration and revocation

- Added callback-path integration in `RentalOIDCAuthenticationBackend.authenticate`: the upstream backend still owns protocol/token validation, while the custom backend records authorization metadata only after the upstream flow returns an authenticated user.
- Viewer groups captured during claim binding are stored with the authorization timestamp after successful login/renewal.
- Failed login or absent viewer membership now removes stale `oidc_authorized_groups` and `oidc_last_authorized_at` session keys.
- RED evidence: `uv run pytest property_rental/rentals/tests/test_oidc.py -q` produced `2 failed, 9 passed`; valid callback metadata was missing (`KeyError`) and stale metadata remained after viewer loss.
- GREEN verification: `uv run pytest property_rental/rentals/tests/test_oidc.py property_rental/rentals/tests/test_production_settings.py -q` produced `20 passed in 8.68s`; `uv run python property_rental/manage.py makemigrations --check --dry-run` produced `No changes detected`; `git diff --check` exited 0.
- Remaining concern: the same pre-existing `staticfiles.W004` warning is emitted for the absent development static directory.
