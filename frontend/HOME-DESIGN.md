# RepoMedic — home page design brief

**Status:** Proposed creative and implementation brief, 29 October 2026  
**Repository:** https://github.com/SGOD-pro/repo-medic · `main` observed at `15a208403b42a41aa4788d2fe77296a703153711`. Fetch again before implementation.  
**Scope:** A new public-facing home page that leads into the existing workflow. It does not authorize deployment, paid repairs, backend changes, or custom execution.

## Product truth

RepoMedic helps developers investigate a dependency-upgrade failure: reproduce it, generate a candidate source patch with a model and sandbox, verify against the tests, and review downloadable patch and evidence. The demonstrated live successes are controlled fixtures. The demo-shop fixture has one collected test; this is not proof of arbitrary repository support. At the observed HEAD, custom-repository configuration can be validated but custom execution is explicitly disabled server-side. Git branch selection is a future feature, not an existing capability. Confirm current behavior again before shipping copy.

**Who:** Developers and technical judges who need to understand the problem and inspect a real demonstration quickly.  
**Desired visitor action:** Open a saved demo result or proceed to the existing configuration workflow.  
**Positioning:** A repair workflow with observable verification and reviewable artifacts. Do not claim it guarantees safe upgrades, improves production reliability, repairs any repository, or replaces human review.

## Reference — what was observed

The user supplied https://www.prismhld.com/?from=canvas and five reference screenshots. Its visible hero uses a split layout: direct text and two actions at left; an architectural flow diagram at right, set over a perspective grid and luminous paths. The supplied screenshots show different states: normal flow and a red database-saturation failure, with colored activity along connections. Subsequent sections include a product preview and a short sequence explaining the process. The reference communicates an abstract technical product through an animated system, not generic stock imagery.

The recorder was unavailable in this session. A browser view and screenshots were inspected, but exact animation timing, pointer interaction, rendering technology and motion transitions were not verified. Do not copy PRISM's identity, text, layout pixel-for-pixel, assets, code, blue visual system or exact scene. Translate the idea of a meaningful animated technical process into original RepoMedic visuals.

## Creative direction: “Trace the repair”

Keep the existing dark forest-green product identity. A developer-oriented editorial page: disciplined grid, confident type, carefully placed light, substantial negative space and one distinctive interactive hero. The 3D scene is a visualization of a repair journey, not a network-architecture diagram or an ornamental rotating blob. The rest of the page is calm and readable. Avoid a stock SaaS page, generic AI buzzwords, excessive glass, glow, repeated floating cards, meaningless metrics and decorative charts.

### Theme and typography

Starting tokens verified in `frontend/src/app/globals.css` at the observed HEAD:

| Role | Value |
| --- | --- |
| Background | `#0D1915` |
| Surface | `#15271F` |
| Raised surface | `#1B3228` |
| Primary / secondary text | `#F7F7F2` / `#A9B8AD` |
| Sage action | `#B7C9AD`, button text `#102D25` |
| Success / failure / warning | `#5FCB8A` / `#E5736A` / `#E0B45A` |
| Informational accent | `#7FB3D5` |

Use existing Manrope for interface and headlines, JetBrains Mono for hashes, paths, code and small stage identifiers. Reuse current semantic tokens and Lucide icons where appropriate. Test actual color contrast; don't assume muted green on green passes. Accent light is restrained, with failure red used only to explain a failure, not paint the whole screen.

## Page structure and copy

1. **Header:** RepoMedic wordmark; links to How it works, View saved demo, and the existing app workspace. One clear action. Keep header compact and keyboard-accessible; do not invent sign-in, pricing or status indicators.
2. **Hero:** Two columns at desktop. Left: headline, plain one-sentence description, primary **View saved demo**, secondary **Configure a repository**, and a small, visible note that custom runs are unavailable. Suggested copy: “See what breaks. Review what fixes it.” Supporting copy: “Reproduce a dependency upgrade failure, inspect a candidate patch, and review the verification evidence.” These are proposed copy, not a verbatim reference-site claim. Right: the interactive repair visualization specified below. On mobile, stack text, actions and a compact scene; never place canvas behind text.
3. **The problem:** One concise editorial section showing the developer's sequence: a passing baseline, dependency upgrade and resulting failure. A small illustrative code/error excerpt can be used only if visibly labeled example and derived from a sanitized fixture; avoid claiming it is a live event.
4. **How RepoMedic works:** Four numbered steps, baseline → reproduce failure → propose patch → verify and review evidence. Use precise, short text and a simple visual progression rather than four identical feature cards. A model-generated patch is a candidate; verification may fail.
5. **Inside the workflow:** A product-preview section using a real screenshot only if available, current, and permitted; otherwise an original semantic UI illustration labeled “Illustrative.” Include a link to the saved run with the exact existing route discovered in code. Do not fabricate working controls or simulate a live repair.
6. **Evidence and limitations:** Explain patch, verification log and evidence JSON as downloadable artifacts where present. State that tests reflect the selected fixture's coverage, that examples are controlled and a developer reviews any patch. Link to a real saved demo. No fabricated benchmarks, quotes, users, savings or billing figures.
7. **Final CTA and footer:** View saved demo / configure repository; a succinct limitation; actual repository/docs links only. No invented subscription or pricing.

## Hero scene — interaction and state design

Create an original low-poly, spatial repair bench: four compact translucent/solid modules representing **Baseline**, **Upgrade**, **Patch**, **Verify**, floating above a very subtle forest-green perspective grid. A thin illuminated trace connects them; sparse particles travel between stages. Place an evidence artifact at the end only after the verify stage in the illustration. Use legible HTML labels adjacent to the canvas rather than relying on tiny rendered text. No exact 3D replica of PRISM.

**Scripted illustration, not live telemetry:** a clearly visible “Illustrative sequence” label must remain present. The scene has four stages:

| State | Scene behavior | Accessible visible label |
| --- | --- | --- |
| 1. Baseline | Soft sage trace reaches a repository/test module | Baseline tests pass |
| 2. Upgrade | Path pauses at dependency module; a localized muted red signal indicates a failure | Upgrade reproduces a failure |
| 3. Candidate | A small patch sheet moves toward a source module; neutral sage return path | A candidate patch is proposed |
| 4. Verification | Path reaches test/evidence module; clean green confirmation | Tests are checked; evidence is available in a successful run |

This is a concept illustrating a supported controlled scenario, not proof that every run succeeds. Failure can also occur during patch generation or verification; narrative copy must say so. The animation must not claim real API state, exact test counts, financial figures or live execution. No automatic repair or API call is triggered by scene interaction.

**Controls:** A visible Play/Pause button and four labeled step buttons beneath or alongside the scene. Clicking/tapping a step selects that scene; `aria-pressed`/equivalent exposes selection, focus is visible, and keyboard users can activate each control. Optional restrained pointer parallax (maximum 4°; no dependency on pointer and no page movement). Under reduced motion show a stable representative state and allow manual step changes without animation. Pause when offscreen/backgrounded; do not trap wheel, touch, focus or page scrolling.

**Motion spec:** Initial stable frame is immediately visible. A deliberate illustrative cycle of roughly 12–16 seconds may progress through the four states with 2–4 seconds of dwell per step, 250–500ms eased transitions and a pause at the end. Exact timings should be tuned after real browser review, not claimed to match PRISM. Play/Pause must remain operable. Avoid flashing, excessive bloom, rapid movement or distracting perpetual motion.

## Implementation and compatibility

Inspect current `frontend` and route/active-tab behavior first: at the observed HEAD, `page.tsx` owns a tab-driven workspace and `?runId=` hydration. Introduce a home view without breaking any existing query deep link: a direct saved-run URL must open/hydrate that run, not get trapped on the landing page. Both home CTAs must navigate to verified existing behavior. Keep task/start/cancel/history/events/artifacts/API contracts unchanged, and preserve the server-side custom-execution gate. No data deletion, paid runs, credential exposure or production changes.

Prefer a small deterministic, client-only 3D scene using existing project capabilities. At observed HEAD Three.js is not a dependency. If genuine 3D is chosen, assess and justify one maintained dependency and bundle impact; use dynamic import and avoid heavy UI frameworks. A lightweight Canvas/SVG/CSS perspective scene is acceptable if it achieves the desired spatial effect; call it 2.5D if that is what is built. Geometry and graphic assets must be original. Do not use screenshots or generated images as functional UI.

Budget targets, to measure rather than promise: scene loads only on home, initial view shows meaningful content without waiting for 3D, aim for ≤250 KB additional compressed scene JS and ≤1 MB total scene assets where feasible, cap pixel ratio, use a small bounded number of particles, pause offscreen, clean up render loops/listeners/contexts and test repeated navigation. Check WebGL support before mounting; provide a designed static SVG/CSS fallback when WebGL, animation, or scripts fail. Reduced-motion and mobile should remain legible and useful without GPU interaction. Avoid scroll hijacking.

## Responsive, accessibility and states

Desktop: balanced split hero; no overlap with header, CTA or diagram. Tablet: maintain readable scene labels and stack before compression makes them too small. Mobile: stack content and diagram; controls remain at least 44px where practical; no horizontal page overflow. Long text and 200% zoom must not clip. Labels, contrast and meaningful status cannot depend only on red/green; canvas is decorative when equivalent HTML explains the sequence. Provide accessible names, correct heading order, visible focus and `prefers-reduced-motion` support.

Loading, error and unsupported graphics states must preserve text, navigation and a static scene. The scene is illustrative, so no real run can appear to be in progress; the saved demo navigation must work without JavaScript animation. Never show synthetic test results as actual evidence.

## Acceptance and validation

- Inspect the reference, current code, `AGENTS.md`, `DESIGN.md` and `UI-UX.md` first; verify actual HEAD and preserve unrelated work.
- Create and inspect one original design target before implementation using the selected UI Taste workflow; correct any imagined capabilities. Compare real renders against it, but do not assert pixel-perfect fidelity without an actual same-size comparison.
- Playwright at 1440×900, 768×1024 and 375×812, plus 320px width and 200% zoom: no clipping, overlap, obstructed CTA or page-level horizontal scroll. Inspect screenshots after fonts/assets load.
- Check CTAs, keyboard, focus, Play/Pause, step controls, reduced motion, scroll behavior, low-performance/static fallback, offscreen cleanup, navigation to app, and `?runId=` saved-run deep-link hydration using fixtures/read-only data. No new model/sandbox request on landing-page load or scene interaction.
- Run applicable lint, typecheck, build and existing tests. Record what was actually run; no claiming production E2E or live 3D verification from static screenshots.
- Preserve original product evidence and existing API/worker behavior. No deploy, real paid repair, provider purchases or database changes without explicit separate authorization.
