# Agent notes

## Versioning

The app version is `MAJOR.MINOR.PATCH` (currently 2.1.2). Bump it once per change merged to `main`, choosing the highest rule that applies:

- **MAJOR**: the change breaks existing data or clients. Examples: a migration that needs manual data work, or a removed or renamed API field.
- **MINOR**: a new user-visible feature or API endpoint.
- **PATCH**: everything else, including fixes, refactors, styling, docs and tests.

Reset the lower digits to zero when a higher one goes up.

Keep the version identical in all of these:

1. `pyproject.toml` (`version`). Run `uv lock` afterwards to update `uv.lock`.
2. `frontend/package.json`. Use `npm version X.Y.Z --no-git-tag-version` so `package-lock.json` follows.
3. `CHANGELOG.md`: add a new top entry `## X.Y.Z — YYYY-MM-DD` with one line per change.

`property_rental/rentals/tests/test_version.py` fails if `pyproject.toml`, `package.json` and the top `CHANGELOG.md` entry disagree. The UI shows the `package.json` version at the bottom of the account menu, on both desktop and mobile. Vite injects it at build time as `__APP_VERSION__`. After merging, tag the commit `vX.Y.Z`.
