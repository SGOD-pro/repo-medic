# Validation report — team kit v0.5

Validated 2026-10-09. These results apply to the supplied contract/fixture kit, not to the unimplemented application.

| Check | Result |
|---|---|
| Foundation unittest suite | 35 tests passed |
| Schema validity, generated-file drift, frozen scenarios, Markdown local links | Passed |
| Generated TypeScript | `tsc --noEmit --strict contracts/generated/types.ts` passed with TypeScript 5.9.3 |
| Python source parsing | All supplied Python source parsed |
| Offline sequential trace | Succeeded with scripted evidence; zero provider calls |
| Offline branch/refinement trace | Succeeded with scripted evidence; zero provider calls |
| Trusted constructed compatibility fixture | Baseline GREEN → upgraded RED → repaired GREEN |
| Package C acceptance gate before implementation | Correctly refused: no actual package acceptance tests |

Validation host: Linux, Python 3.12, Node 24.19.0 for standalone TypeScript compilation. Team-selected Node 22 baseline and Windows/Antigravity integration are not yet tested; foundation F2 confirms them and records exact locks/commands.

35 tests include subcase checks for verifier gates and all nine scenario traces. They validate contracts, fake harness behavior and SQLite constraints. They do not establish real model repair quality, real provider lifecycle/billing, actual app security, completed frontend/API/engine behavior or benchmark success.

No Token Factory API keys or Sandboxes used for these checks. Dependency downloads used package registries; Token Factory credits were not spent. Real compatibility probe and live repair remain required gates.
