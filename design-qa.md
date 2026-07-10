**Source visual truth**

- `/var/folders/c8/nm0lr61j7_1cqbb3t1bfbdlw0000gn/T/codex-clipboard-f0a722ec-bf05-4051-8037-e6ead888dd20.png`

**Implementation evidence**

- Desktop: `/private/tmp/plateau-logo-final-desktop.png`
- Mobile: `/private/tmp/plateau-logo-final-mobile.png`
- Side-by-side comparison: `/private/tmp/plateau-logo-comparison.png`
- Viewports: default desktop viewport (1280 × 720 capture) and 390 × 844 mobile
- State: PLATEAU building search dialog, facility-name tab selected, empty query

**Full-view comparison evidence**

- The source and implementation use the same vertical orange PaperCAD wordmark, white page, centered search panel, tab state, and close control.
- The implementation intentionally moves the wordmark from the source's upper-left position to the visual center of the left margin, as permitted by the requested placement discretion. This balances the search panel without reducing whitespace.

**Focused region comparison evidence**

- Desktop wordmark: fully visible, vertically centered, and separated from the search panel.
- Mobile wordmark: compact and anchored 18px from the visible left and bottom edges; it does not overlap the search form or close control.

**Required fidelity surfaces**

- Fonts and typography: existing PaperCAD font family, weight, tracking, line height, and white-on-brand treatment are preserved; responsive size is clamped from 56px to 72px on desktop and set to 32px on mobile.
- Spacing and layout rhythm: desktop uses a centered left-margin anchor; mobile uses a bottom-left anchor. Search UI spacing is unchanged.
- Colors and visual tokens: existing `--primary-color`, panel background, and white foreground are unchanged.
- Image quality and asset fidelity: the wordmark remains code-native brand text already present in the source implementation; no raster substitution or new approximation was introduced.
- Copy and content: all visible copy is unchanged.

**Findings**

- No actionable P0/P1/P2 differences remain.

**Comparison history**

- Initial mobile pass found a P2 clipping issue: rotation placed part of the wordmark outside the left viewport edge.
- Fix: changed the mobile anchor from `left: 18px` to `left: 52px`, accounting for the rotated element's 32.8px visual width.
- Post-fix evidence: the measured bounding box is left 19.2px, right 52px, top 668.4px, bottom 826px at 390 × 844; the final mobile screenshot confirms it is fully visible.

**Interaction and console checks**

- Opened the building search from the home screen and closed it with the close button; the dialog was removed successfully.
- No console errors were emitted by the final production build on port 8082. A prior development-port IndexedDB keymap error was isolated to port 8081 and is unrelated to this CSS change.

**Follow-up Polish**

- None required for this change.

final result: passed
