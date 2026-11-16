# Lessons

## 2026-11-14 — Verify the release base before starting work

Fetch the remote and tags before creating a feature branch. Compare the checkout with the fetched default branch; a recent fetch does not advance local `main`. Base new work on the current remote default branch unless the user specifies another base. Derive the next version from that branch and release tags, rather than stale checkout files or the version quoted in agent notes. Production state requires deployment evidence; Git alone does not establish what is deployed.

## 2026-11-16 — Separate observed mortgage facts from usable estimates

When the owner requests estimated mortgage history, calculate and label monthly splits instead of stopping at annual aggregates. Keep statement cash totals exact, preserve the rate changes and accepted balance anchors, and separate unpaid accrued interest and financed fees from cash payments. Replace aggregates rather than adding overlapping monthly rows. Prefer authoritative statement balances when the owner approves a correction; consolidate equivalent opening/year-end snapshots rather than leaving adjacent duplicates.
