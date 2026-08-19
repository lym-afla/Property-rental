---
name: Rent
description: A quiet graphite ledger for rental-property bookkeeping, where color is signal.
colors:
  instrument-paper: "oklch(1 0 0)"
  instrument-void: "oklch(0.145 0 0)"
  graphite-panel: "oklch(0.205 0 0)"
  graphite-raised: "oklch(0.269 0 0)"
  graphite-rule: "oklch(0.97 0 0)"
  graphite-line: "oklch(0.922 0 0)"
  graphite-mid: "oklch(0.556 0 0)"
  graphite-ring: "oklch(0.708 0 0)"
  ledger-red: "oklch(0.577 0.245 27.325)"
  ledger-red-dark: "oklch(0.704 0.191 22.216)"
  instrument-steel: "oklch(0.48 0.085 245)"
  instrument-steel-dark: "oklch(0.74 0.074 245)"
  signal-blue: "#2563EB"
  signal-amber: "#D97706"
  signal-green: "#059669"
  signal-violet: "#7C3AED"
  signal-red: "#DC2626"
  signal-cyan: "#0891B2"
  signal-magenta: "#C026D3"
  signal-lime: "#65A30D"
  signal-slate: "#475569"
typography:
  display:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 2rem
  title:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.375rem
  body:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.25rem
  label:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1rem
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  pill: "26px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.graphite-panel}"
    textColor: "{colors.instrument-paper}"
    rounded: "{rounded.lg}"
    padding: "10px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "oklch(0.199 0 0)"
  button-outline:
    backgroundColor: "{colors.instrument-paper}"
    textColor: "{colors.instrument-void}"
    rounded: "{rounded.lg}"
    padding: "10px"
    height: "32px"
  button-destructive:
    backgroundColor: "oklch(0.577 0.245 27.325 / 10%)"
    textColor: "{colors.ledger-red}"
    rounded: "{rounded.lg}"
    padding: "10px"
    height: "32px"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.instrument-void}"
    rounded: "{rounded.lg}"
    padding: "10px"
    height: "32px"
  card:
    backgroundColor: "{colors.instrument-paper}"
    textColor: "{colors.instrument-void}"
    rounded: "{rounded.xl}"
    padding: "16px"
  badge-secondary:
    backgroundColor: "{colors.graphite-rule}"
    textColor: "{colors.graphite-panel}"
    rounded: "{rounded.pill}"
    padding: "8px"
    height: "20px"
  badge-destructive:
    backgroundColor: "oklch(0.577 0.245 27.325 / 10%)"
    textColor: "{colors.ledger-red}"
    rounded: "{rounded.pill}"
    padding: "8px"
    height: "20px"
---

# Design System: Rent

## Overview

**Creative North Star: "The Quiet Ledger"**

Rent is a bookkeeping instrument, not a marketing surface. The chrome is machined from a single graphite ramp — hairline rules, flat panels, compact controls — so that recorded figures and charts are the loudest things on any screen. Nothing decorative stands between the operator and the numbers; the interface's job is to be legible at a glance during a recurring review pass, then get out of the way.

Density is deliberate: 32px controls, 14px body text, 16px card interiors, and tables that read like a ledger's ruled lines. Depth is drawn with 1px hairlines and rings rather than shadows, which keeps every surface on one machined plane. Light and dark modes are both first-class: paper-white vs near-black grounds with the same grey ramp inverted.

Color lives in the data layer: the chart palette mints nine saturated hues, and that is where saturated color stays. Chrome actions are graphite ink; one desaturated hue — Instrument Steel — traces wayfinding only: focus rings, active navigation and tabs, and link text. Steel never fills; buttons, segments, checkboxes, and badges stay graphite.

**Key Characteristics:**
- Graphite Instrument chrome: a single achromatic OKLCH ramp, hairline structure, zero shadows
- Ledger density: compact 32px controls, 14px body, dense tables with accounting-style numerics
- Geist Variable is the only typeface; hierarchy is built purely from size, weight, and greyness
- Saturated color is born in the chart palette and stays there; Instrument Steel traces chrome wayfinding; actions are graphite
- First-class loading, empty, and error states on every data surface

## Colors

A machined graphite ramp carries the whole interface; saturation is minted by the chart palette and spends most of its life inside charts.

### Primary
- **Instrument Steel** (oklch(0.48 0.085 245) / #2F628A; dark oklch(0.74 0.074 245) / #83B0D7): The wayfinding accent (`--signal`, also driving `--ring`). Colors focus rings, active navigation and tabs, and link variants — at 6.49:1 on paper and 7.8–8.6:1 on the dark surfaces. It is never a fill: actions stay graphite.
- **Graphite Panel** (oklch(0.205 0 0)): The `--primary` action fill restored — primary buttons, the active dashboard segment, checkbox checked state, and default badges. White text on it holds 17.9:1.

### Secondary
- **Ledger Red** (oklch(0.577 0.245 27.325)): The single semantic color — destructive actions and invalid states, almost always as a 10–20% tint with red text, never a solid red fill. Dark mode uses Ledger Red Dark (oklch(0.704 0.191 22.216)) under the same doctrine.

### Tertiary
- **Signal Amber** (#D97706), **Signal Green** (#059669), **Signal Violet** (#7C3AED), **Signal Red** (#DC2626), **Signal Cyan** (#0891B2), **Signal Magenta** (#C026D3), **Signal Lime** (#65A30D), **Signal Slate** (#475569): The fixed categorical chart palette, assigned in this exact order by series index (stroke 2.5px). Beyond nine series the palette extends through ten reserved hues, then generated golden-angle HSL steps — never re-shuffled per chart.
- In dark mode four hues lift to hold ≥3:1 on the dark card surface: Blue → #3B82F6, Violet → #8B5CF6, Red → #EF4444, Slate → #64748B (the extended palette lifts fuchsia → #D946EF, deep rose → #F43F5E, deep indigo → #818CF8, sky → #0284C7, deep green → #15803D, indigo → #6366F1). Hue order and series semantics never change between themes.

### Neutral
- **Instrument Paper** (oklch(1 0 0)): Light-mode ground and card surface.
- **Instrument Void** (oklch(0.145 0 0)): Dark-mode ground and light-mode ink (body text).
- **Graphite Panel** (oklch(0.205 0 0)): Dark-mode card surface; light-mode primary action fill.
- **Graphite Raised** (oklch(0.269 0 0)): Dark-mode secondary and muted fills.
- **Graphite Rule** (oklch(0.97 0 0)): Light-mode secondary/muted/accent fills — quiet row fills, ghost hovers, table footers.
- **Graphite Line** (oklch(0.922 0 0)): Light-mode borders and input strokes; dark-mode primary ink.
- **Graphite Mid** (oklch(0.556 0 0)): Muted foreground — labels, captions, inactive navigation.
- **Graphite Ring** (oklch(0.708 0 0)): Mid-ramp grey; dark-mode muted text. Not the focus ring — focus belongs to Instrument Steel.

### Named Rules
**The Steel Signal Rule.** Chrome is Graphite Instrument grey. Instrument Steel (oklch(0.48 0.085 245) / dark oklch(0.74 0.074 245)) is the single wayfinding accent — focus rings, active navigation and tabs, and link text — and it never fills: buttons, segments, checkboxes, and badges stay graphite. Saturated color lives only in the chart palette; no chrome color outside the steel and the chart hues may be invented.

**The Tinted Danger Rule.** Destructive actions use a 10% Ledger Red tint with red text (hover 20%); solid red fills are reserved for nothing and used nowhere.

**The Two Grounds Rule.** Light and dark are composed from one system, not mirrored by inversion: the same graphite ramp, the same series order, the same accent. Only lightness lifts — never a dark-only hue, never a re-ordered palette. Both themes set `color-scheme` so native surfaces (scrollbars, caret, form controls) follow the ground.

## Typography

**Display Font:** Geist Variable (sans-serif fallback)
**Body Font:** Geist Variable (sans-serif fallback)

**Character:** A single neo-grotesque variable face with a slightly technical, instrument-panel demeanor — quiet at text sizes, confident and tabular-feeling at figure sizes. The pairing drama is zero on purpose; the drama is reserved for numbers.

### Hierarchy
- **Display** (700, 1.5rem/2rem): Page titles (`h1`) and KPI figures — the loudest voice on any surface.
- **Headline** (500, 1.25rem/1.75rem): Detail-page titles (property name, tenant name) set inside cards.
- **Title** (500, 1rem/1.375rem): Card titles; shrinks to 0.875rem on small cards.
- **Body** (400, 0.875rem/1.25rem): All default text, table cells, form controls, navigation links.
- **Label** (500, 0.75rem/1rem): KPI labels (muted), captions, badges; mobile tab labels drop to 0.6875rem.

### Named Rules
**The Single Family Rule.** Geist Variable is the only typeface. Hierarchy is created exclusively through size, weight, and greyness (muted foreground) — never a second family, never letterspacing tricks.

**The Figure First Rule.** On any surface, the most important number may equal the page title in size (1.5rem/700) but never exceeds it; everything else steps down quietly. Numerals in tables are accounting-formatted and right-aligned.

## Layout

A top ledger bar (56px, hairline bottom border) holds the wordmark, five data-surface links (Dashboard, Properties, Tenants, Transactions, FX), and an account dropdown under the username. Content sits in a centered container with 16px gutters and 24px vertical padding. Navigation links: active = Instrument Steel at medium weight; inactive = Graphite Mid, darkening to ink on hover.

On mobile the top links are replaced by a fixed bottom tab bar — five equal columns, hairline top border, Instrument Paper at 95% opacity with backdrop blur, safe-area padding, 44px touch targets, 11px labels. Desktop-first density otherwise: controls stay 32px tall; only touch targets in navigation get the 44px minimum.

The dashboard adds a section nav (Overview, Income & Costs, Portfolio, Risk) as a segmented grid of buttons — two columns on mobile, four from 640px — active segment rendered as a primary button, inactive as outline. KPI cards sit in a summary row; chart cards stack below in the container's single column. Spacing runs on Tailwind's 4px grid; card interiors use 16px; sibling gaps 16–24px.

## Elevation & Depth

The system is flat by conviction. There are no shadow tokens; structure comes from 1px hairlines — cards wear `ring-1` in foreground at 10% opacity, tables rule their rows with border-b, the navbar and tab bar draw single hairlines. The only spatial effects are the mobile tab bar's backdrop blur and a 1px downward press-translate on active buttons. Focus is visible and physical: a 3px Instrument Steel ring at 50% opacity with a matching border shift — the accent doubles as the wayfinding signal.

### Shadow Vocabulary
None. Depth is tonal: hover states lift via Graphite Rule fills (muted at 50%), never via shadow.

### Named Rules
**The Hairline Rule.** Every boundary is a 1px line or ring. If a design feels like it needs a drop shadow, it needs a hairline or a muted fill instead.

## Shapes

One corner family: a 10px base radius (`--radius: 0.625rem`) with a stepped scale — 6px (sm), 8px (md), 10px (lg) for controls, 14px (xl) for cards, up to 26px at the top of the scale. Buttons and inputs use the 10px step; their small sizes clamp to 8–10px. Cards use 14px and clip their media with `overflow-hidden`. The one exception is the badge, a full pill (26px radius, 20px tall). Borders are always 1px; fills are opaque greys in light mode and translucent white overlays in dark mode.

## Components

### Buttons
- **Shape:** gently rounded (10px radius), compact heights — default 32px, sm 28px, xs 24px, lg 36px; horizontal padding 10px, 6px icon gap
- **Primary:** Graphite Panel fill, Instrument Paper text (17.9:1), 14px/500; hover darkens the fill 10% toward ink (oklch(0.199 0 0))
- **Hover / Focus:** 150ms transitions; focus-visible draws the 3px/50% ring; active presses down 1px; disabled at 50% opacity
- **Outline:** hairline Graphite Line border on Instrument Paper, fills Graphite Rule on hover — the workhorse for table row actions and segmented nav
- **Ghost:** transparent, fills Graphite Rule on hover — navbar and tool usage
- **Destructive:** 10% Ledger Red tint with red text (20% on hover) per the Tinted Danger Rule

### Chips
- **Style:** 20px-tall pills (26px radius), 12px/500 text, 8px horizontal padding; default = graphite fill with paper text, secondary = Graphite Rule fill with panel ink, destructive = red tint, outline = hairline border
- **State:** used for statuses and row tags; interactive chips brighten their fill on hover

### Cards / Containers
- **Corner Style:** 14px radius, `overflow-hidden`
- **Background:** Instrument Paper wearing a 1px ring at 10% foreground opacity (dark: Graphite Panel)
- **Shadow Strategy:** none — see The Hairline Rule
- **Border:** ring only; footers add a top hairline over a Graphite Rule 50% band
- **Internal Padding:** 16px standard (`--card-spacing`), 12px on small cards

### Inputs / Fields
- **Style:** 32px tall, 10px radius, 1px Graphite Line stroke, transparent ground, 14px text (16px on mobile to defeat iOS zoom), placeholder in Graphite Mid
- **Focus:** border shifts to the ring color plus the 3px/50% focus ring
- **Error / Disabled:** invalid states adopt the red border and 20% red ring; disabled fields dim to 50% with a muted fill

### Navigation
- **Top bar:** 56px, hairline bottom border; wordmark semibold in ink; links 14px — active in Instrument Steel/medium, inactive Graphite Mid; account actions live in a dropdown under the username
- **Theme control:** a Theme submenu inside the account dropdown (Light / Dark / System radio items, trigger icon follows the active theme). Preference is local to the device (next-themes localStorage); a pre-paint script in both HTML shells applies the class before first render, so there is no flash of the wrong ground
- **Mobile:** fixed bottom tab bar, five equal columns, blurred paper, 44px targets, 11px labels, safe-area aware; active tab in Instrument Steel
- **Segmented section nav:** grid of outline buttons with the active segment as a primary (graphite) button
- **Tabs:** active trigger text in Instrument Steel over the neutral pill; line-variant underline in Instrument Steel

### KPI Figure Card
The signature unit: a Card whose title is a 12px-muted label, whose content is one Display-size (24px/700) accounting-formatted figure, and an optional 12px muted description line. Skeletons occupy the figure slot while loading — the value is a ReactNode by design.

### Analytics Chart Card
The second signature: a titled Recharts card fed by typed backend series. Series colors assign strictly by index from the signal palette (2.5px strokes) and follow the resolved theme — the dark ground lifts only the hues that need it, never the order. Axes and grid are token-driven (muted-foreground lines, muted grid), zero-line references inherit `currentColor`, and the tooltip is a popover token surface — the entire chart layer flips grounds without a single hardcoded chrome color. Every card implements the full state machine — loading skeleton, empty message, error with retry, and a table alternative carrying the same accounting-formatted numbers.

### Tables
- **Style:** 14px cells, hairline row rules, header row bottom border, hover fills Graphite Rule at 50%; footer repeats as a muted band at 50% with medium-weight totals
- **Behavior:** horizontally scrollable in their container; numerics right-aligned and accounting-formatted; selection fills muted

## Do's and Don'ts

### Do:
- **Do** keep controls compact — 32px default height for buttons and inputs, 14px body text — the ledger density is the identity.
- **Do** use Instrument Steel for wayfinding — focus rings, active navigation and tabs, link text; it never fills, and buttons stay graphite.
- **Do** implement all four data states (loading skeleton, empty, error with retry, content) on every data surface.
- **Do** right-align and accounting-format every numeric column; figures never lie about sign or currency.
- **Do** use tinted red for danger (10% fill, red text) and hairlines for structure.
- **Do** check every new surface on both grounds — Instrument Paper and Instrument Void are equals, and charts must hold ≥3:1 on the dark card surface.

### Don't:
- **Don't** introduce a second typeface or a display serif; hierarchy comes from size, weight, and greyness only.
- **Don't** add drop shadows to cards, menus, or popovers — hairlines and muted fills carry depth.
- **Don't** color chrome with hues outside the signal palette, and never reorder the nine chart colors.
- **Don't** exceed Display size (24px/700) for figures or headings; nothing shouts past the page title.
- **Don't** loosen density into roomy 44px+ controls outside touch navigation.
