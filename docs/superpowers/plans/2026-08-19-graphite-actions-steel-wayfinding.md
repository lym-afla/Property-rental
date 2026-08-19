# Graphite Actions + Steel Wayfinding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Signal Blue accent with graphite primary actions plus an Instrument Steel wayfinding accent (design E2, approved 2026-08-19).

**Architecture:** Token-level change: revert `--primary` to the original graphite, add a new `--accent` token (steel) consumed only by wayfinding classes (active nav/tabs, link variants) and `--ring`; charts untouched. A new e2e contract test pins the wiring so the accent cannot silently regress.

**Tech Stack:** Tailwind CSS 4 token layer (`frontend/src/index.css`), Playwright e2e, vitest.

## Global Constraints

- `--primary`: light `oklch(0.205 0 0)`, dark `oklch(0.922 0 0)` (verbatim reverts)
- `--primary-foreground`: light `oklch(0.985 0 0)`, dark `oklch(0.205 0 0)`
- `--accent` / `--ring`: light `oklch(0.48 0.085 245)`, dark `oklch(0.74 0.074 245)`
- Charts (`chartTheme.ts`, `useChartTheme`, axis theming) must not be touched
- Steel applies only to: focus rings (via `--ring`), active nav/tabs, `link` variants of Button/Badge
- The dashboard section-nav active segment, checkbox checked, badge default, primary buttons stay graphite (`--primary`)

---

### Task 1: E2E accent contract test (fails first)

**Files:**
- Modify: `frontend/e2e/investment-dashboard.spec.ts` (append at end)

**Interfaces:**
- Produces: test `'chrome accent contract: graphite actions and steel wayfinding'` used as the pass/fail gate for Tasks 2–3.

- [ ] **Step 1: Append the failing test**

```ts
test('chrome accent contract: graphite actions and steel wayfinding', async ({ page }) => {
  // Light theme: graphite primary token, steel accent token, wired correctly.
  await page.goto('/login')
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible()
  const light = await page.evaluate(() => {
    const cs = getComputedStyle(document.documentElement)
    const probe = document.createElement('span')
    probe.style.color = 'var(--accent)'
    document.body.appendChild(probe)
    const accent = getComputedStyle(probe).color
    probe.remove()
    return {
      primary: cs.getPropertyValue('--primary').trim(),
      ring: cs.getPropertyValue('--ring').trim(),
      accent: cs.getPropertyValue('--accent').trim(),
      loginBg: getComputedStyle(document.querySelector('form button')!).backgroundColor,
      accentComputed: accent,
    }
  })
  expect(light.primary).toBe('oklch(0.205 0 0)')
  expect(light.accent).toBe('oklch(0.48 0.085 245)')
  expect(light.ring).toBe('oklch(0.48 0.085 245)')

  // Active nav uses the accent token, not primary.
  await page.goto('/')
  await page.getByRole('heading', { name: 'Investment dashboard' }).waitFor()
  const navWiring = await page.evaluate(() => {
    const active = document.querySelector('header nav a[aria-current="page"]') as HTMLElement | null
    if (!active) return { active: 'missing' as const }
    const probe = document.createElement('span')
    probe.style.color = 'var(--accent)'
    document.body.appendChild(probe)
    const accent = getComputedStyle(probe).color
    probe.remove()
    return { active: getComputedStyle(active).color, accent }
  })
  expect(navWiring.active).toBe(navWiring.accent)

  // Dark theme: lifted steel accent.
  await page.evaluate(() => localStorage.setItem('theme', 'dark'))
  await page.goto('/')
  await page.getByRole('heading', { name: 'Investment dashboard' }).waitFor()
  const dark = await page.evaluate(() => ({
    primary: getComputedStyle(document.documentElement).getPropertyValue('--primary').trim(),
    accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
  }))
  expect(dark.primary).toBe('oklch(0.922 0 0)')
  expect(dark.accent).toBe('oklch(0.74 0.074 245)')
  await page.evaluate(() => localStorage.setItem('theme', 'light'))
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx playwright test e2e/investment-dashboard.spec.ts -g "accent contract" --project=desktop`
Expected: FAIL — `--primary` still `oklch(0.5461 0.2152 262.88)`, `--accent` empty.

### Task 2: Tokens

**Files:**
- Modify: `frontend/src/index.css` (`:root` block, `.dark` block, `@theme inline` block)

**Interfaces:**
- Produces: `--accent` / `--color-accent` tokens used by Task 3's `text-accent` classes.

- [ ] **Step 1: Edit `:root`**

```css
    --primary: oklch(0.205 0 0);
    --primary-foreground: oklch(0.985 0 0);
    --accent: oklch(0.48 0.085 245);
    --ring: oklch(0.48 0.085 245);
```
(replacing the current `--primary: oklch(0.5461 0.2152 262.88);` and `--ring: oklch(0.5461 0.2152 262.88);` lines; `--primary-foreground` already correct)

- [ ] **Step 2: Edit `.dark`**

```css
    --primary: oklch(0.922 0 0);
    --primary-foreground: oklch(0.205 0 0);
    --accent: oklch(0.74 0.074 245);
    --ring: oklch(0.74 0.074 245);
```
(replacing `--primary: oklch(0.70 0.154 258.7);`, keeping `--primary-foreground` as-is, replacing `--ring: oklch(0.70 0.154 258.7);`)

- [ ] **Step 3: Add the utility mapping in `@theme inline`**

After the `--color-primary: var(--primary);` line add:

```css
    --color-accent: var(--accent);
```

### Task 3: Wayfinding classes

**Files:**
- Modify: `frontend/src/components/layout/AppLayout.tsx` (two NavLink className callbacks)
- Modify: `frontend/src/components/ui/tabs.tsx` (two class strings)
- Modify: `frontend/src/components/ui/button.tsx` (link variant)
- Modify: `frontend/src/components/ui/badge.tsx` (link variant)

- [ ] **Step 1: AppLayout desktop nav** — `'text-primary font-medium'` → `'text-accent font-medium'`
- [ ] **Step 2: AppLayout mobile tab bar** — `'font-medium text-primary'` → `'font-medium text-accent'`
- [ ] **Step 3: tabs.tsx** — `data-active:text-primary` → `data-active:text-accent`; `after:bg-primary` → `after:bg-accent`
- [ ] **Step 4: button.tsx link variant** — `link: "text-primary underline-offset-4 hover:underline"` → `link: "text-accent underline-offset-4 hover:underline"`
- [ ] **Step 5: badge.tsx link variant** — same `text-primary` → `text-accent` swap
- [ ] **Step 6: Run the accent contract test** — `npx playwright test e2e/investment-dashboard.spec.ts -g "accent contract" --project=desktop` → PASS
- [ ] **Step 7: Unit suite** — `npm test` → 227+ passed (no unit test asserts these classes)

### Task 4: Baselines, full e2e, detector

- [ ] **Step 1:** `PW_CHANNEL=chrome npx playwright test e2e/investment-dashboard-visual.spec.ts --update-snapshots` (chrome changed → all baselines regenerate, incl. dark)
- [ ] **Step 2:** `PW_CHANNEL=chrome npx playwright test e2e/investment-dashboard-visual.spec.ts` → 6 passed; `npx playwright test e2e/investment-dashboard.spec.ts` → all passed (incl. existing dark-mode test asserting `#3B82F6` chart fills — charts untouched)
- [ ] **Step 3:** `npm run lint && npm run build` → clean
- [ ] **Step 4:** impeccable detector over changed files → `[]`
- [ ] **Step 5:** Commit implementation: `feat: restore graphite actions with steel wayfinding accent`

### Task 5: DESIGN.md + sidecar sync

- [ ] **Step 1: DESIGN.md** — frontmatter: `button-primary` background back to `{colors.graphite-panel}`; add `accent-steel`/`accent-steel-dark` color entries; rule rename: Spreading Ink → **Steel Signal Rule** (graphite chrome, one steel wayfinding accent, saturated color only in charts); Colors/Components/Navigation prose updated (buttons graphite; active nav/tabs/links steel; focus rings steel)
- [ ] **Step 2: `.impeccable/design.json`** — colorMeta adds accent-steel entries; button/badge/nav snippets revert to graphite fills with steel active-nav; narrative rules/text updated to match
- [ ] **Step 3:** Validate JSON, commit docs: `docs: record the steel signal design system`

## Self-Review

- Spec coverage: tokens ✓ (Task 2), wayfinding list ✓ (Task 3 items 1–5 map to the spec's four bullet points + ring), charts untouched ✓ (no chart file in any task), pixel/e2e assertions ✓ (Task 1 + existing suites Task 4), DESIGN sync ✓ (Task 5), rollout ✓ (commits).
- No placeholders; all edits shown with exact strings.
- Names consistent: `--accent`, `--color-accent`, `text-accent` throughout.
