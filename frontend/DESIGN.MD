# RepoMedic — frontend design system

Status: proposed · 29 October 2026  
Based on the existing forest-green interface and user screenshots at `main` 2946510. These are design targets for a refactor, not claims that the current frontend already complies. Companion: `UI-UX.md`.

## Design direction

A calm, precise developer workspace: forest-green foundations, light sage controls, readable typography and a modest density appropriate for code repair. The product's real workflow provides the character. Use open space and alignment before adding a border or card. Avoid nested panels, decorative chips, generic metric grids, large all-caps eyebrows and simulated telemetry. A bento grid is useful for distinct run/result information, not as a container for filler.

The existing app uses Manrope for interface text and JetBrains Mono for code and technical values. Retain these fonts and provide system fallbacks. Use Lucide icons already in the project, consistently sized and paired with labels where needed. No new font, icon or component dependency is required.

## Color tokens

These values come from `frontend/src/app/globals.css`; preserve them as the starting palette and measure contrast in actual rendered states. Do not claim every existing combination is accessible without checking it.

| Role | Token | Existing value | Usage |
| --- | --- | --- | --- |
| Page background | `--bg` | `#0D1915` | Main workspace |
| Surface | `--surface` | `#15271F` | Distinct grouped regions |
| Raised surface | `--surface-raised` | `#1B3228` | Selected or interactive surfaces |
| Primary text | `--text` | `#F7F7F2` | Headings and content |
| Secondary text | `--text-muted` | `#A9B8AD` | Supporting copy and labels |
| Primary action | `--accent` | `#B7C9AD` | Main button, focus accents |
| Button text | `--button-text` | `#102D25` | Text on sage button |
| Success | `--pass` | `#5FCB8A` | Evidence-backed success |
| Error | `--fail` | `#E5736A` | Failure and field errors |
| Warning | `--warn` | `#E0B45A` | Disabled/unavailable, uncertainty |
| Information | `--info` | `#7FB3D5` | Informational status |
| Border | `--border` | `rgba(183,201,173,.16)` | Default separators |
| Strong border | `--border-strong` | `rgba(183,201,173,.32)` | Interactive and focus boundaries |

Use semantic names consistently in components rather than copying hex values. Contrast target: WCAG AA 4.5:1 for normal text, 3:1 for large text and applicable non-text UI indicators. Measure blended colors on their real surfaces, including disabled and placeholder states. Adjust tokens when measurements require it; never solve insufficient contrast by making important copy smaller or lighter.

## Type and spacing

| Element | Target |
| --- | --- |
| Page title | 28–32px desktop, 24–28px mobile; 600 weight |
| Section title | 18–20px; 600 weight |
| Body | 14–16px with 1.45–1.6 line height |
| Field label / supporting text | 14px label; 12–14px supporting copy, high enough contrast |
| Code, SHA, version, logs | JetBrains Mono, 12–14px; tabular digits where useful |

Use Manrope for normal labels and content; do not turn every label into uppercase monospace. Use consistent spacing based on 4/8/12/16/24/32/48px. Group related items tightly; give sections 24–32px separation. Target a 1200–1280px maximum content width, with 24–32px desktop and 16–20px mobile gutters. Long IDs must wrap or truncate with a copy/full-view option; logs and diffs may scroll within clearly marked containers.

## Layout and shell

Use one compact header with RepoMedic identity, current navigation, history and documentation. Navigation labels describe destinations; current location remains clear at narrow widths. Avoid a persistent provider-status strip unless status is actually known. Responsive navigation must not clip controls or require horizontal page scrolling.

Desktop pages may use a 12-column layout: configuration fields use a balanced 2-column grid; demo selection uses a wider task list and narrower selected summary; run uses stage list plus candidate/log content; results use a compact summary with a full-width patch. These ratios are guidelines: preserve readable line lengths and working controls rather than forcing equal cards. Mobile uses a single column, explicit action hierarchy and appropriately sized controls. Sticky regions must not cover content or trap keyboard focus, and must account for header height and short screens.

## Components

- **Buttons:** one primary action per context; secondary outline or text actions for alternatives. Minimum 44px target height for touch, visible focus, disabled and loading states. Keep button copy short and specific. Destructive actions clearly named and distinct.
- **Forms:** visible labels, required marker, example placeholders, concise help text. Use 44px inputs, clear focus and inline errors tied with `aria-describedby` and `aria-invalid`. Group logically; avoid a long wall of repeated guidance. Validation status must describe what was actually checked.
- **Cards:** one subtle border and 8–12px radius for grouped content. Prefer section dividers to a card inside a card. No strong shadows, decorative gradients or colored glows. Existing 20px cards may be reduced consistently during the refactor.
- **Status:** concise text plus icon and color. Queued, running, succeeded, failed, cancelled, unavailable and disconnected are distinct; connection state is not run state. Use neutral styling for unknown and never imply verified success from placeholder data.
- **Lists and tables:** use rows for history and task lists where scanning matters; allow meaningful metadata, selected state and keyboard access. Empty, loading and error views should tell the user the next action.
- **Logs and diffs:** use a dark inset region, monospace, bounded height and intentional overflow. Preserve text selection; escape data. Provide download/copy only for available content.
- **Notices:** one compact contextual notice, with a specific action when helpful. Avoid alarming decorative banners and repeated policy text.

## Page compositions

1. **Home:** restrained product introduction, two actions and a brief workflow; controlled demo limitations visible.
2. **Configure:** title + short explanation, compact gate notice, balanced form grid, inline errors, actions immediately after fields. No fixed right-side action detached from the form.
3. **Demo tasks:** concise saved-result links, task list, selected summary and settings. Keep the start action visible and tied to the selection; do not display unverified runner information.
4. **Run:** status header, stage timeline, candidate panel and event log as an intentional grid. Prioritize current activity; show unavailable data honestly. Cancel only for a nonterminal run.
5. **Results:** clear outcome followed by evidence summary, patch and artifact actions. Use a bento arrangement only for meaningful evidence; no invented numbers. Failure and cancellation layouts retain useful partial results.
6. **History:** compact searchable/filterable list only where supported by data; status, mode and time when available. No claim of per-user privacy without authentication.

## Interaction and motion

Keep transitions brief and functional (roughly 120–180ms for hover or expand), honor `prefers-reduced-motion`, and avoid entrance choreography. Preserve browser back/forward and saved-run links. Prevent duplicate starts and preserve form values when appropriate. Do not display an unconfirmed live connectivity or sandbox-health badge. Never show a completed run with active controls.

## Verification and handoff

For each page, review default, loading, empty, error, success, disabled and long-content states that can actually occur. Render at representative desktop and mobile widths, including 320px and 200% zoom. Check focus order, contrast, readable text, overflow, sticky actions and reduced motion. Compare screenshots against a stable target and report the viewport, data mode and known deviations. A successful build is not visual verification.

Implementation must retain API contracts, saved links and server-side execution gating. Review every displayed metric against real response/evidence fields. Existing screenshots and generated concept imagery are references, not evidence of a working implementation. Do not add integrations, spend, deployment or data deletion as part of the visual work.
