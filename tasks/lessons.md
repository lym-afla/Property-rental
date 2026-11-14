# Lessons

## 2026-11-14 — Verify the release base before starting work

Fetch the remote and tags before creating a feature branch. Compare the checkout with the fetched default branch; a recent fetch does not advance local `main`. Base new work on the current remote default branch unless the user specifies another base. Derive the next version from that branch and release tags, rather than stale checkout files or the version quoted in agent notes. Production state requires deployment evidence; Git alone does not establish what is deployed.
