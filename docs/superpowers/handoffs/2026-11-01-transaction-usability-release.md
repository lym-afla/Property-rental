# Rent 2.2.0 release handoff

Candidate: PR #8, `codex/rent-transactions-implementation`.
Approved scope: transaction sorting, native currency defaults, former-tenant toggle, teal home browser identity.

## Implementation and local evidence

- 285 frontend component/API tests pass.
- 510 backend tests pass, one existing skip.
- Frontend lint and production build pass.
- Django system checks pass; migration drift check reports no changes.
- Production image builds; `scripts/container_smoke.py` passes, including a nested route's SVG icon.
- 38 browser checks pass on a serial full run across desktop, tablet and mobile; 10 platform/viewport-specific skips. A preceding concurrent run had five tablet Vite dynamic-import failures; all five passed in the full serial rerun.
- The final independent review found three delayed-data defects. Reproducing tests failed before each fix and passed afterwards: stale name sorting, USD manual override, unresolved former-tenant toggle. No critical findings or deferred minor findings.

Windows Chrome regenerated the transaction-cell baselines in run 41328275673. Four images changed as expected from header widths; each was visually inspected. The temporary capture workflow was removed. Final PR CI must pass against the committed baselines before merge. Linux intentionally skips the Windows visual tests.

## Decisions made during implementation

- Preserve custom accounting periods on edit. The previous effect rewrote the stored period on initial load; keeping it would silently alter historical entries.
- Match the Tenants page's existing UTC date convention for vacancy classification.
- When an assigned tenant is still loading, disable the former-tenant toggle until its status is known; retain the assignment.
- Leave the pre-existing null-first-name rendering outside this change; backend name fields are non-null.
- Keep release verification distinct from source review: passing local tests do not establish deployment acceptance.

## Release procedure

Use the current Life OS runbooks, not an ad hoc container restart:

- `docs/operations/rent-production-release-runbook.md`
- `docs/operations/app-production-release-runbook.md`

1. Approve and merge PR #8 after all checks pass. Reconcile version if main changed meanwhile.
2. Tag the merged source commit `v2.2.0`. Verify Rent CI and image publication for that exact full SHA.
3. Verify the active release and recovery predecessor support `lifeos-rent-deploy-contract: no-deps-v1`.
4. From clean, synchronized Life OS main, run `node scripts/release/promote-app.mjs rent --source <merged-source-sha> --host <operator-ssh-host>`.
5. Execute the printed `release-app rent` command from `/opt/life-os/deploy/current` on the VPS.
6. Require the encrypted backup and isolated candidate restore rehearsal. Do not use `--skip-backup`.
7. Verify image agreement and acceptance. Unrelated services must retain their container IDs, images and restart counts.
8. Check signed-in sorting, currency defaults, former-tenant toggle and icon without saving test transactions in production.
9. Append the acceptance record in Life OS. Record exact source/release references, verification and browser results.

No schema migration, SQLite import, identity relinking or catalogue change is required. Recovery follows the runbook's previous-source promotion and rehearsal.

## Production access boundary

No merge, release tag, image publication or production change was performed during implementation. The local Life OS checkout contains the `no-deps-v1` contract. Live predecessor verification remains pending.

The runbook's default SSH alias `livvy` does not resolve on this workstation. The configured `ylifeos-codex` account rejects release inspection (`ERROR:SSH_COMMAND_DENIED`); it is an Origination-specific forced-command account. Use an authorized operator route for Rent deployment. Do not weaken or bypass that account's restrictions.
