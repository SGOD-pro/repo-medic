# Build phases and start gates

Design v0.5. Task IDs map to docs/specs/<ID>.md and work-package ownership. Dates are not commitments; evidence gates determine readiness.

| Phase | Work | Start / exit |
|---|---|---|
| Foundation | F0–F6, lead+C with A/B review | Start now; exit common BASE_SHA, locks/contracts/commands, connected fake thin workflow, tiny provider facts recorded |
| Parallel package build | A1–A6, B1–B7, C1–C5 and offline C7; D1–D3 optional | Start F6; independent fakes eliminate cross-package runtime prerequisites |
| Package acceptance | Named tests/builds + contracts + handoff | Exit no invented fields/other-owner edits, each owned feature verified offline |
| Integration | I1–I3 led by lead | B host+C engine+A UI connected, failure/cancel/reconnect/security/offline trace passes |
| Real sequential | C6 + I4 | First real pinned repair, fresh verifier/evidence; no fake fallback; measured cost |
| Branching | C7 + A/B display/persistence acceptance | Serial/sequential already works; branch isolation/refinement/gates pass offline then bounded live |
| Evaluation | D4–D5 | D tooling can start F6; real quality measurements start after I4/C7 depending on arm |
| Release | I5, demo/deploy/evidence | Clean clone, locks, live access, reserve budget, final video and truthful limitations |

A/B/C can build at the same time after foundation. C needs provider facts early to implement adapters, not B's running API. C tests with standalone host harness. D needs result/interface contract to build runner; actual results require real C. With three people, lead does D after integration, C assists experiment execution.

Suggested critical path: F1 contracts → F2 scaffold → F4 fake thin connection → F6 distribute → C sequential / B durable host / A run reducer → I1 connected offline → I4 live sequential → branching and controlled comparison → release. Provider spike F5 can run alongside scaffold without forcing A/B paid access.

Per-task completion: exact named checks actually written/run, mode/commit recorded, output/limitations preserved. Do not tick complete from generated documentation or fake fixtures alone. Shared edits are foundation tasks; downstream packages request changes. Never send teammates only their Markdown while omitting repo/contracts.
