# Graphite actions + steel wayfinding (E2) — design

Date: 2026-08-19
Status: approved by operator after pixel-verified gallery review
 (`artifacts/accent-gallery/gallery2.html`, direction E2)

## Context

Production currently ships the Signal Blue accent (`--primary` = oklch(0.5461 0.2152 262.88), the Signal Blue spread of 2026-08-16). The operator rejected it: the blue primary button reads as "old Bootstrap", and it diverged from the app's initial graphite-button identity. A candidate gallery (rendered via transport-level token rewriting, pixel-verified) explored five directions; the operator converged on **E2: graphite actions + steel wayfinding**, with the Steel Blue hue (#2F628A) retained from candidate D as a signal color only.

## Decision

- **Actions are graphite again.** `--primary` reverts to the original values: light `oklch(0.205 0 0)`, dark `oklch(0.922 0 0)`; `--primary-foreground` reverts to light `oklch(0.985 0 0)`, dark `oklch(0.205 0 0)`. Primary buttons, the active dashboard section segment, checkbox checked state, and default badges return to the pre-accent look.
- **A new `--accent` token carries wayfinding: Instrument Steel.** Light `oklch(0.48 0.085 245)` (#2F628A, 6.49:1 on paper), dark `oklch(0.74 0.074 245)` (#83B0D7, 7.82:1 on the dark card, 8.63:1 on the dark ground). Both clear WCAG AA for text and 3:1 for controls.
- `--ring` becomes the steel accent in both themes (focus wayfinding), and `@theme inline` gains `--color-accent: var(--accent)` so `text-accent` utilities exist.

## Where steel applies (complete list)

1. Focus rings — every control, automatic via the `--ring` token.
2. Active top-nav link and active mobile tab (`AppLayout.tsx`): `text-primary` → `text-accent`.
3. Tab active text and line-variant underline (`tabs.tsx`): primary → accent.
4. `link` variants of Button and Badge: `text-primary` → `text-accent`.

Nothing else. Buttons, segments, checkboxes, and badges never carry the steel; steel never fills.

## Explicitly unchanged

- Chart palettes (light and dark), `chartTheme.ts`, `useChartTheme`, axis theming — the blue-led chart layer is permanent.
- Hover mechanics (the color-mix darkening from the Signal Blue work is AA-safe for graphite and stays).
- Density, typography, dark-mode machinery, backend, `PRODUCT.md`.

## Tests and verification

- Unit suite must pass unchanged (no test asserts accent colors on nav).
- New pixel-level e2e assertions in `investment-dashboard.spec.ts`: the login button's computed background must be graphite; the active nav link's computed color must be steel. This makes any future silent accent regression fail CI.
- Regenerate Playwright visual baselines (chrome changes affect them); light and dark.
- Run the impeccable detector once over changed files.
- Sync `DESIGN.md` + `.impeccable/design.json`: the Spreading Ink Rule becomes the **Steel Signal Rule** — graphite chrome, one steel wayfinding accent, saturated color lives only in charts. Frontmatter tokens updated (`button-primary` back to graphite-panel; new accent entries).

## Rollout

Single frontend commit on `main`; follows the established CI → image publish → Life OS promotion flow when the operator requests it.
