# Paper-CAD Design System

**Status:** Draft  
**Version:** 1.0  
**Principle:** Less, but better. Honest to paper.

Paper-CAD is a CAD tool for making architectural paper models. The primary artifact is not a screenshot—it is a printed sheet (SVG/PDF) that will be cut, folded, and assembled.

We design like a Japanese studio shaping a German industrial tool: quiet surfaces, explicit hierarchy, obsessive consistency. The viewport is the work; the UI is the instrument.

**Workflow:** Model → Unfold → Layout → Export → Build.

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
- **The sheet is the product:** the UI must serve print accuracy, assembly clarity, and trust.
- **Do not rely on color alone:** printing may be grayscale; semantics must survive in line style and labeling.

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

### 2.3 Unfold Output Semantics (SVG/PDF)

- Output classes should remain stable and legible in black & white:
  - Face outlines: `.face-polygon`
  - Tabs: `.tab-polygon`
  - Fold hints: `.fold-line`
  - Cut hints: `.cut-line`
  - Page boundaries: `.page-border` / `.page-separator`
- Do not rename output selectors without updating exporters (e.g. multi-page detection depends on `.page-border`).

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

- Use `--transition-fast`/`--transition-base`/`--transition-slow`.
- Respect `prefers-reduced-motion`: disable non-essential animations.

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

## 9. Change Process

1. Update tokens in `frontend/public/index.css` (both themes).
2. Update this document when new tokens or patterns are introduced.
3. Run formatting: `cd frontend && npm run format`.

## 10. Legacy Refactor Checklist

- Replace hardcoded spacing with `--spacing-*`.
- Replace hardcoded borders with `--border-color`.
- Prefer semantic tokens over palette tokens.
- Verify light/dark themes and all interaction states.
