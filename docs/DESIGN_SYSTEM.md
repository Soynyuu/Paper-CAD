# Paper-CAD Design System

**Version:** 1.0 (Draft)
**Philosophy:** "Precision meets Modernity"

Paper-CAD is a tool for precision. Its design should reflect the clarity, accuracy, and focus required by its users. The interface is not just a wrapper; it is the drafting table. It should be invisible when you are working, and obvious when you need tools.

## 1. Design Principles

*   **Content First:** The 3D model/canvas is the hero. UI elements float above it or sit quietly to the side.
*   **High Contrast & Legibility:** Technical data must be readable. Use high contrast for text, distinct colors for actions.
*   **Tactile Feedback:** Buttons should feel clickable (hover/active states). Inputs should clearly indicate focus.
*   **Consistent Rhythm:** Use the 4px baseline grid for all spacing and sizing.

## 2. Design Tokens

The following tokens map to CSS Custom Properties defined in `index.css`.

### 2.1 Colors

#### Brand
Used for primary actions (Save, Submit, Select).
*   **Primary:** `var(--brand-primary)` (`#ff6633`) - The "Paper-CAD Orange". Energetic, visible.
*   **Secondary:** `var(--brand-secondary)` (`#ff5533`)
*   **Tertiary:** `var(--brand-tertiary)` (`#ff8844`)

#### Neutrals (Surface & Text)
Used for backgrounds, borders, and text.
*   **Background:** `var(--neutral-0)` (Light: `#ffffff`, Dark: `#121212`)
*   **Surface:** `var(--neutral-50)` (Light: `#f5f5f5`, Dark: `#1f1f1f`) - Panels, Cards.
*   **Border:** `var(--neutral-200)` - Subtle dividers.
*   **Text Main:** `var(--neutral-900)` - Primary content.
*   **Text Muted:** `var(--neutral-500)` - Labels, secondary info.

#### Semantics
*   **Success:** `var(--success-color)` (`#2ecc71`)
*   **Warning:** `var(--warning-color)` (`#ff8b35`)
*   **Error:** `var(--danger-color)` (`#ec5f5f`)
*   **Info:** `var(--info-color)` (`#3498db`)

### 2.2 Typography

**Font Family:**
*   UI: `"Noto Sans JP", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
*   Code/Data: `Monaco, Consolas, "Courier New", monospace` (Recommended addition)

**Scale:**
*   `xs` (12px): Metadata, tiny labels.
*   `sm` (14px): Standard UI text, dense lists.
*   `base` (16px): Body text, inputs.
*   `lg` (19px): Section headers.
*   `xl` (24px): Page titles.

### 2.3 Spacing & Geometry

**Grid Unit:** 4px
*   `xs` (4px)
*   `sm` (8px)
*   `md` (16px) - Standard padding.
*   `lg` (24px)
*   `xl` (32px)

**Radius:**
*   `xs` (2px): Sharp, technical feel. Used for inner elements.
*   `sm` (4px): Standard buttons, inputs.
*   `md` (8px): Cards, dialogs.

### 2.4 Shadows & Depth

*   `shadow-sm`: Subtle lift for buttons.
*   `shadow-md`: Dropdown menus, tooltips.
*   `shadow-lg`: Modals, floating panels.

## 3. Component Guide

### Buttons
*   **Height:** 32px (Compact), 40px (Standard).
*   **Primary:** Solid Brand Orange background, White text.
*   **Secondary:** Transparent background, Border `neutral-300`, Text `neutral-800`.
*   **Ghost:** Transparent background, Text `neutral-600`, Hover `neutral-100`.

### Inputs
*   **Background:** `neutral-0` (or `neutral-100` in dark mode).
*   **Border:** 1px solid `neutral-300`.
*   **Focus:** Border color `brand-primary`, Box-shadow `shadow-focus`.
*   **Label:** `text-sm`, `font-medium`, `neutral-700`.

### Panels & Cards
*   **Background:** `neutral-0` (or `neutral-50` floating).
*   **Border:** 1px solid `neutral-200`.
*   **Header:** `neutral-50`, `border-bottom` 1px solid `neutral-200`.

## 4. Implementation Guidelines

### CSS Modules
We use CSS Modules for component scoping.
1.  **Import Styles:** `import styles from './MyComponent.module.css';`
2.  **Use Variables:** Always reference variables, never hardcode hex values.
    ```css
    .container {
        padding: var(--spacing-md);
        background-color: var(--neutral-0);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-sm);
    }
    ```

### Theme Support
The application supports Light and Dark modes via `[theme="dark"]` on `:root`.
*   Testing: Toggle the attribute on the `<html>` tag to verify your component looks good in both.

### Refactoring Legacy Code
When touching old components:
1.  Replace hardcoded px margins with `var(--spacing-*)`.
2.  Replace `#ccc` borders with `var(--border-color)`.
3.  Replace black/white text with `var(--neutral-900)` / `var(--neutral-0)`.
