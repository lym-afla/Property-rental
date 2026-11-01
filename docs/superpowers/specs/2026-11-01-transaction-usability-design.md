# Rent transaction usability and browser identity

Status: approved by the user after builder review on 2026-11-01.

## Intent and scope

Make routine transaction entry and review easier in Rent, as part of Ylifeos: sortable transaction headers, property-native currency defaults, current tenants by default with an explicit way to include former tenants, and a recognisable browser icon. Preserve historical records and use the existing Rent-only production release process.

This is one bounded application change, expected to release as 2.2.0 from the current 2.1.2 baseline because sorting is a new user-visible capability. Recheck the baseline before merge. No schema or API changes are expected.

## Approaches and decisions

- Tenant selection: user chose a “Show former tenants” toggle beside the existing selector over a separate former-tenant action. It reuses loaded tenant data and does not fetch or change eligibility when the transaction date changes.
- Sorting: reuse the existing TanStack table sorting rather than adding server-side ordering. The page already loads the transaction list and paginates locally. User confirmed clickable column headers.
- Currency: use the selected property's native currency for new transactions, keeping the currency selector editable. User confirmed this behavior.
- Identity: user selected A, the teal home, over the navy door and monochrome R. Reference preview: `.superpowers/brainstorm/3519447-1793550705/content/rent-controls-and-icons.html`. The production asset must be self-contained and must not depend on that preview.
- Deployment: use the established app-only Life OS promotion and release tooling, rather than changing the shared stack or deploying an ad hoc container.

## Transaction sorting

Expose keyboard-accessible sorting buttons with visible direction indicators and appropriate aria-sort semantics for Date, Property, Tenant, Category, Amount, Period, and Comment. Actions are not sortable. Newest date first remains the default. Sort the complete filtered result before pagination, and return to the first page on sort changes.

Compare ISO dates and periods chronologically, names and category display labels alphabetically, and amounts numerically, including negative expenses. Amount sorting uses recorded values without FX conversion; the currency remains visible beside each amount. Missing tenants and empty values receive deterministic ordering. Sorting need not survive reloads in this change. Preserve existing filters and their URL behavior.

Builder discretion: use page-specific headers or an explicit opt-in shared-table feature, whichever is simpler; do not silently alter other pages' behavior. Choose deterministic tie breaking and sensible empty-value placement.

## Currency defaults

In a new transaction, selecting a property sets its native currency. Each actual property change resets this default to the newly selected property's currency. Users may then override it. Other field changes and data refetches must not undo a manual override.

For a form opened with a preselected property, use that property's currency immediately when its data is available. Before any property is selected, retain the existing USD fallback; changing user preference behavior is out of scope.

Editing a transaction preserves its recorded currency on initial load. An explicit property change may use the new property's currency; merely opening or saving an existing transaction must not change it. Apply consistent behavior anywhere the shared transaction form is used.

## Tenant selection

Default new-transaction choices to non-vacated tenants of the selected property. Match the existing Tenants page's vacancy convention: a lease ending before today is former; an end date today or later, or no end date, is not former. Reuse its date helper where practical. Do not tie this to the transaction date or introduce additional requests. Future leases retain the existing page's non-vacated classification in this scope.

With “Show former tenants” checked, include former tenants of the same property and label them “Former tenant”; show current tenants first. Without a property, disable the tenant selector. Tenant remains optional, with an explicit unassigned choice. Show useful empty-state text when no eligible tenant exists.

An existing transaction assigned to a former tenant must show and retain that selection on edit. Initialize the toggle on for such edits. If the user turns it off while a former tenant is selected, clear the optional selection visibly; do not retain a hidden selected value. Changing property clears any tenant that does not belong to the newly selected property. Toggling or editing must never modify the tenant record or hide historical transactions from list filters.

## Browser identity

Use the selected teal rounded square (#0f766e), white house silhouette, and teal doorway, preserving the preview's simple geometry. Implement as a self-contained SVG favicon, with any fallback formats the existing delivery setup requires. Confirm legibility at 16 and 32 pixels on light and dark browser chrome.

Wire the icon into both the Vite development entry and the Django production shell. Production must serve it through the application's static asset pipeline, including nested routes. Use “Rent” as the consistent base tab title. Per-page dynamic titles shown in the mockup are illustrative and are not required. App-wide branding and the Ylifeos catalogue icon are outside this change.

## Verification

Add meaningful regression coverage for ascending/descending sorting across pagination, numeric negative/positive amounts, name-based columns, property currency initialization and changes, manual override preservation, editing historical values, current/former tenant visibility, property changes, and retained existing former-tenant assignments. Reuse existing test infrastructure.

Run focused tests, then required backend/frontend checks and existing relevant browser scenarios. Verify the favicon in the built production shell, not only Vite. Run the production container smoke checks where available and rely on exact-commit CI evidence for release. Check version consistency and update both lockfiles and CHANGELOG.

## Ylifeos release plan

Follow `/home/yl/code/yl-life-os/docs/operations/rent-production-release-runbook.md` and its referenced application runbook, re-reading current instructions before execution.

1. Implement and review on an isolated Rent branch. Finish tests, update the version once, and prepare a reviewable change.
2. Merge through the repository's supported process, tag the resulting release commit v2.2.0 (or the reconciled version), and verify passing Rent CI and image publication for that exact full source SHA.
3. Verify the active Life OS release and recovery predecessor meet the Rent dependency-isolation contract (`no-deps-v1`). From a clean, synchronized Life OS main, use `scripts/release/promote-app.mjs rent --source <sha>` to resolve and promote the immutable image digest. Only the Rent application manifest entry changes.
4. Use the printed `release-app rent` command: backup, isolated candidate restore rehearsal, stage, deploy Rent only, verify manifest/runtime image agreement, and run acceptance. Do not skip backup or rehearsal. Shared services must retain their container identities and restart counts.
5. Complete safe signed-in browser checks for sorting, transaction form defaults without saving test records, and the browser icon. Append release evidence to the existing Rent acceptance record.
6. If recovery is necessary, use the documented previous-source promotion path and rehearsal; do not erase data or invent a parallel rollback mechanism.

Production action follows concrete review of the verified release candidate and existing authorization; resolve any missing deployment authorization at that final boundary. Do all authorized preparation first. Never claim deployment success without the release and acceptance evidence.

## Non-goals and failure conditions

No transaction-date-dependent tenant fetching, historical data rewriting, currency conversion for sorting, shared-infrastructure redesign, identity relinking, imports, or catalogue lifecycle changes. A release that restarts unrelated Ylifeos services, loses historical tenant assignments, overwrites manual currency choices on refetch, or only fixes the icon in development fails this design.
