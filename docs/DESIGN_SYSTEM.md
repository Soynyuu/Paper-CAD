# Paper-CAD Design System

**Status:** Draft  
**Version:** 1.0  
**Principle:** Less, but better. Honest to paper.

Paper-CAD is a CAD tool for making architectural paper models. The final artifact is a physical model. The printed sheet (SVG/PDF) is not the end—it is an interface to a build process that the app must actively support.

Digital is not decoration here. Digital is leverage: instant feedback, reversible decisions, and continuity across 3D ↔ 2D ↔ paper. The goal is a new assembly experience where the sheet can “talk back” through a device.

We design like a Japanese studio shaping a German industrial tool: quiet surfaces, explicit hierarchy, obsessive consistency. The viewport is the work; the UI is the instrument.
Everything is measured. Nothing is decorative.

**Workflow:** Model → Unfold → Layout → Export → Build.

**Keywords:** MUST / SHOULD / MAY define requirement levels in this document.

## 1. Principles (Dieter Rams, adapted)

1. **Useful, not clever:** Prefer clarity and speed over novelty.
2. **Understandable:** Controls look and behave like controls. No hidden “magic”.
3. **Unobtrusive:** The canvas/viewport stays primary; UI stays quiet.
4. **Honest:** Don’t fake affordances. Don’t hide limitations.
5. **Durable:** Avoid trendy visuals that age fast.
6. **Thorough:** Every component defines its states (hover/active/focus/disabled/loading).
7. **Accessible:** Keyboard-first, sufficient contrast, visible focus.
8. **Efficient:** No heavy effects that compete with 60fps interaction.
9. **Consistent:** Same tokens, same patterns, same outcomes.
10. **As little design as possible:** Remove until only the necessary remains.

### 1.1 Paper-CAD-specific: Material & Output

- **Paper is the medium:** assume prints in real-world conditions (cheap printers, imperfect cutting, human hands).
- **The sheet is the contract:** it must be print-accurate, assembly-true, and trustworthy.
- **Do not rely on color alone:** printing may be grayscale; semantics must survive in line style and labeling.
- **Continuity wins:** face identity and intent must survive 3D ↔ 2D ↔ paper ↔ device.

## 2. Paper-First Product Context (Architectural Models)

### 2.1 What “Good” Means Here

- Correct scale and page size without surprises.
- Clear assembly intent (tabs, fold/cut cues, stable face numbers, orientation).
- Fast verification (what changed, what will be printed, what will be built).

### 2.2 Workflow Implications for UI

1. **3D modeling is the source.**
2. **2D unfolding is the bridge** (faces must remain identifiable across 3D ↔ 2D).
3. **Page layout is a constraint** (A4/A3/Letter, margins, page count).
4. **Export is the deliverable** (SVG/PDF should be print-ready).
5. **Assembly is the end-user test** (if it’s confusing on paper, it’s a UI bug).

### 2.3 Digital Assembly Experience (Device Interaction)

Paper assembly is a mapping problem (“Which face is this?”). Digital should eliminate that question.

- The app MUST provide a fast way to locate a face from a printed sheet:
  - scan a printed QR/deep link, or
  - search by face number / ID.
- When a face is located, the app MUST show a consistent, unambiguous context:
  - the face highlighted in 3D and 2D,
  - orientation cues (front/back, mirrored, page orientation),
  - the page and position on the sheet (when available).
- The interaction MUST be low-friction on mobile (one-handed, large targets, readable in dark mode).
- Linking MUST degrade gracefully: if a QR cannot resolve, manual lookup still works.

### 2.4 Unfold Output Semantics (SVG/PDF)

- Output classes should remain stable and legible in black & white:
  - Face outlines: `.face-polygon`
  - Tabs: `.tab-polygon`
  - Fold hints: `.fold-line`
  - Cut hints: `.cut-line`
  - Page boundaries: `.page-border` / `.page-separator`
- Multi-page SVGs MUST include a `.page-border` element per page as a stable marker; treat selectors as a public contract.

### 2.5 Print Reality Checklist

- Units are physical (mm). Prefer explicit units over implicit assumptions.
- Respect margins: treat at least 10mm as non-printable safe area.
- Assume monochrome printing is common: line meaning must survive without color.
- Prefer warnings over surprises: if output will be clipped, scaled, or mirrored, say it before export.

### 2.6 Print Output Specification (Commercial Bar)

This section defines what “print-ready” means. If export violates these, the UI is lying.

#### 2.6.1 Units & Conversion

- Output geometry is physical. Prefer **mm** end-to-end.
- If SVG uses px-based coordinates, conversion MUST be explicit and consistent:
  - 96 DPI assumption: `1mm = 3.78px`
  - If this changes, update exporters and this document together.

#### 2.6.2 Page, Safe Area, and Layout

- Supported page formats MUST match:
  - A4: 210×297mm, A3: 297×420mm, Letter: 216×279mm
- Default safe margin MUST be **10mm** on all sides (printer reality).
- Layout MUST keep critical geometry, labels, and QR codes inside the safe area.
- If content will overflow or be scaled, the UI SHOULD show a clear warning before export.

#### 2.6.3 Line System (Monochrome-First)

The print output MUST remain understandable in pure black & white.

- Line meaning MUST not depend on color; use a combination of **weight** and **dash pattern**.
- Recommended baseline (mm):
  - Face outline (`.face-polygon`): 0.35mm solid
  - Cut line (`.cut-line`): 0.25mm solid
  - Fold line (`.fold-line`): 0.25mm dashed (e.g. 6mm on / 3mm off)
  - Tab outline (`.tab-polygon`): 0.20mm dashed (e.g. 3mm on / 2mm off)
  - Page border (`.page-border`): 0.15mm dashed, light (not competing with geometry)
- Strokes SHOULD use `vector-effect: non-scaling-stroke` so scaling never destroys legibility.
- Output SHOULD avoid heavy fills; paper needs whitespace to breathe.

#### 2.6.4 Typography & Labeling in Output

- Default output font MUST use a generic, portable stack (no external font dependency).
- Labels MUST be readable at arm’s length on A4:
  - Minimum text size: 2.2mm (~8pt) for secondary labels
  - Recommended: 2.8–3.2mm (~10–11pt) for primary labels
- Face numbers MUST be legible but not aggressive; avoid bright red as the only channel.

#### 2.6.5 Sheet Metadata (Quiet, Useful)

Every exported sheet SHOULD include a minimal, quiet metadata block:

- Model name / identifier
- Scale (e.g. `1:1`, `1:50`)
- Page format + orientation
- Page number / total pages
- Export timestamp or version (for reproducibility)

#### 2.6.6 Stability & Compatibility

- Output class names (`.face-polygon`, `.tab-polygon`, `.fold-line`, `.cut-line`, `.page-border`) MUST be stable.
- Multi-page detection MUST use a stable page boundary marker (`.page-border`).
- QR or linking graphics (if used) SHOULD be vector (paths), not raster.
- If QR/deep links are included, placement MUST avoid tabs and fold/cut lines; for tiny faces, prefer a per-page index panel.

## 3. Scope & Source of Truth

- **Tokens:** CSS Custom Properties in `frontend/public/index.css`.
- **Themes:** `theme="light"` / `theme="dark"` on the root element (`<html>` / `:root`).
- **Components:** `frontend/packages/chili-ui` should consume tokens (prefer semantic tokens first).

## 4. Token Rules (Non-Negotiable)

- New or modified UI code **MUST** use `var(--...)`. No hard-coded hex colors or “random” spacing values.
- Any new token **MUST** have values for both themes (`:root[theme="light"]` and `:root[theme="dark"]`).
- Prefer **semantic tokens** (e.g. `--background-color`, `--border-color`, `--panel-background-color`, `--button-*`) over raw palette tokens (`--neutral-*`).
- If a component needs a token that doesn’t exist, add it to `frontend/public/index.css` instead of improvising.

## 5. Foundations (Tokens)

### 5.1 Color

**Brand**

- `--brand-primary`: primary actions and focus emphasis (use sparingly; one accent is enough).
- `--brand-secondary`, `--brand-tertiary`: accents; avoid using multiple brand colors in the same view.

**Neutrals (Palette)**

- `--neutral-0` … `--neutral-900`: use as a palette, but prefer semantic tokens below.

**Semantic**

- `--success-color`, `--info-color`, `--warning-color`, `--danger-color`
- Use only for status and feedback. Do not use semantics to “decorate” layouts.

**Semantic (Recommended Defaults)**

- Surface & layout: `--background-color`, `--panel-background-color`, `--control-background-color`
- Text: `--foreground-color`
- Borders: `--border-color`
- Interaction: `--hover-background-color`, `--active-background-color`

**Contrast**

- Text should meet WCAG AA as a baseline (4.5:1 normal text, 3:1 large text).
- Never rely on color alone for meaning; pair with icon and/or copy.

### 5.2 Typography

- Primary stack is set on `html, body` in `frontend/public/index.css`.
- Default UI text today is `14px` (dense and practical for CAD).
- Use the token scale when styling components: `--font-size-xs`/`sm`/`base`/`lg`/`xl`.
- Numeric data, IDs, and code-like strings should use a monospace stack for alignment:
  - `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`

### 5.3 Spacing & Geometry

- Base unit is 4px (`--spacing-xs`).
- Use `--spacing-xs`/`sm`/`md`/`lg`/`xl` for almost everything.
- `--spacing-10` and `--spacing-12` exist for legacy alignment. Avoid introducing new “special” spacing.

### 5.4 Radius

- Default: `--radius-sm` (4px).
- Keep radii consistent within a component; mixing radii reads as indecision.

### 5.5 Shadows, Focus, and Layering

- Elevation: `--shadow-sm` (controls), `--shadow-md` (menus/popovers), `--shadow-lg` (dialogs).
- Focus ring: `--shadow-focus` is required with `:focus-visible` on interactive elements.
- Layering: use `--z-*` tokens. Never hardcode `9999`.

### 5.6 Motion

Motion is functional. It communicates state changes, preserves continuity, and reduces cognitive load. It must never be decorative.

- Use `--transition-fast`/`--transition-base`/`--transition-slow` (default: `--transition-base`).
- Prefer animating `opacity` and `transform`. Avoid layout-affecting properties (`width`, `height`, `top`, `left`, `margin`) and expensive effects (`filter`, `backdrop-filter`) unless justified.
- During direct manipulation (dragging, resizing, scrubbing), transitions SHOULD be disabled to keep the tool crisp.
- Keep motion small: avoid large travel; no bounce/elastic easing in production UI.
- Avoid infinite or attention-seeking animations; they compete with drafting.
- Respect `prefers-reduced-motion`: non-essential motion MUST be removed; essential meaning MUST remain via non-animated cues (contrast, outline, label).

Example (pattern, not a global mandate):

```css
@media (prefers-reduced-motion: reduce) {
  .animated {
    transition-duration: 0ms !important;
    animation: none !important;
  }
}
```

## 6. Component Guide

### 6.1 Buttons

- Heights: 32px (compact), 40px (standard).
- Variants:
  - **Primary:** `--brand-primary` background, `--neutral-0` text.
  - **Secondary:** `--button-background` background, `--button-border-color` border, `--button-text-color` text.
  - **Ghost:** transparent background; hover uses `--button-hover-background`.
  - **Danger:** use `--danger-color` for destructive actions (do not use brand orange).
- States (must exist): hover, active, focus (`:focus-visible`), disabled, loading.
- Icon-only buttons: minimum 32×32 hit area, and always an accessible name.

### 6.2 Inputs

- Align height with buttons (32px/40px).
- Background: `--control-background-color`.
- Border: `1px solid var(--border-color)`.
- Focus: border `--brand-primary` + `--shadow-focus`.
- Error: border + helper text use `--danger-color`.
- Readonly: use `--opacity-readonly` (but keep text contrast).

### 6.3 Panels & Cards

- Background: `--panel-background-color`.
- Border: `1px solid var(--border-color)`.
- Header: `--panel-header-background`.
- Resizable panels: drag handles must be visible and have an 8px+ hit area.

### 6.4 Dialogs, Popovers, Tooltips

- Shadows: dialog `--shadow-lg`, popover `--shadow-md`.
- Layering: `--z-modal-backdrop`/`--z-modal`/`--z-popover`/`--z-tooltip`.
- Keyboard: focus trap for dialogs; `Esc` closes when safe.

## 7. Accessibility & Interaction

- Keyboard-first: every control must be reachable and operable via keyboard.
- Focus: never remove focus indication; use `:focus-visible` + `--shadow-focus`.
- Targets: 32px minimum; small icons must include padding.
- Errors: state what happened, why, and what the user can do next.

## 8. Implementation (CSS Modules)

We use CSS Modules for component scoping.

```css
.container {
  padding: var(--spacing-md);
  background-color: var(--panel-background-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}

.container:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}
```

## 9. Quality Gates (What “Commercial” Means)

If any item fails, the change is not done.

### 9.1 UI (App)

- No hard-coded hex colors or arbitrary spacing in new/modified UI code.
- Light and dark themes both acceptable; focus ring visible (`:focus-visible` + `--shadow-focus`).
- Keyboard navigation works; no focus traps outside dialogs.
- Text contrast meets WCAG AA as a baseline.
- Labels are tool-like: no decorative emoji, no novelty copy in production UI.
- Motion is minimal and purposeful; no infinite animations; respects `prefers-reduced-motion`.

### 9.2 Output (SVG/PDF)

- Page size correct; safe margin respected; no clipped geometry.
- Meaning survives monochrome printing (line style/weight + labels).
- Face identity is stable between 3D and 2D (numbers/labels don’t reshuffle unexpectedly).
- Export is deterministic enough to diff (no random IDs unless necessary).

### 9.3 Assembly (Device Interaction)

- From paper: scan QR or search by face number/ID → correct face context within 2 steps.
- Cross-highlighting between 3D and 2D is consistent (no ambiguous “selected” state).
- Works on mobile: touch targets, readable typography, no tiny hit areas.
- Failure modes are polite: broken links show a recovery path (manual face lookup).

### 9.4 Evidence (PR)

- UI changes: screenshots for light/dark.
- Unfold/export changes: attach exported PDF/SVG (and ideally a quick photo of a real print).
- Assembly features: short screen recording + one photo of a real build-in-progress.

## 10. Change Process

1. Update tokens in `frontend/public/index.css` (both themes).
2. Update this document when new tokens or patterns are introduced.
3. Run formatting: `cd frontend && npm run format`.

## 11. Legacy Refactor Checklist

- Replace hardcoded spacing with `--spacing-*`.
- Replace hardcoded borders with `--border-color`.
- Prefer semantic tokens over palette tokens.
- Verify light/dark themes and all interaction states.
