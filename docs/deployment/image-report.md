# Production image report

Measured locally on 2026-07-31 for `property-rental:life-os`.

| Metric | Value |
| --- | ---: |
| Docker-reported local image size | 566 MB |
| OCI image size from CI helper | 125,329,866 bytes |
| Gzipped OCI archive from CI helper | 124,659,412 bytes |

The byte measurements are produced by:

```powershell
pwsh -File scripts/ci_container.ps1
```

The apparent difference between Docker Desktop's local image size and the OCI
archive byte count is expected; Docker reports expanded local image storage
while the CI helper records the exported OCI artifact and gzipped archive.

## Largest runtime layers

From `docker history property-rental:life-os`:

| Layer | Approx. size | Notes |
| --- | ---: | --- |
| `/opt/venv` copy | 261 MB | Locked production Python dependencies. Largest packages are Django/DRF, scientific/analytics support such as pandas/numpy/networkx, PostgreSQL client dependencies, yfinance, and transitive packages. |
| Debian bookworm base | 85.3 MB | Base OS layer from `python:3.11-slim-bookworm`. |
| Python runtime install | 52.3 MB | CPython 3.11 slim runtime layer. |
| App prune/static ownership layer | 15.1 MB | Final filesystem cleanup and ownership adjustment. |
| Collected static assets | 14.1 MB | WhiteNoise-served Django/static frontend assets. |
| Compiled frontend source copy | 1.48 MB | Vite manifest and hashed SPA assets copied before collectstatic. |

Runtime filesystem spot check:

| Path | Size |
| --- | ---: |
| `/opt/venv` | 223 MB |
| `/app` | 15 MB |

Do not remove required analytics dependencies merely to improve the number.
Future image-size work should focus on understanding the `/opt/venv` dependency
tree and whether any production dependency can be safely made optional.

## Runtime content assertions

`scripts/container_smoke.py` verifies:

- no Node.js or npm;
- no uv;
- no gcc or cc compiler;
- no Python lint/format tooling packages such as `djlint`, `cssbeautifier`, or
  `jsbeautifier`;
- no package-manager cache directories;
- no local SQLite database files;
- no frontend source maps;
- no tests, Playwright/e2e directories, or fixtures under `/app`;
- no third-party package `tests` directories, Playwright/e2e directories, or
  fixtures under `/opt/venv`; Django's required runtime `django.test` module is
  retained because Django REST Framework imports it at runtime;
- no committed `.env*` file;
- non-root process user;
- production settings use PostgreSQL only.
