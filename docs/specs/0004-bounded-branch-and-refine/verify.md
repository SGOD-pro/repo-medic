# Verify: Bounded branch and refine · spec 0004 · updated 2026-10-11

_Steps derived from spec 0004 acceptance criteria. `/check verify` runs these; `/test` locks the durable ones._

## Commands

- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_repair_routes_sequential_vs_branch_refine` → passes and routes between sequential and branch refine repair → AC-1
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_exhaustion_when_all_branches_and_refinements_fail` → passes and enforces maximum three candidate branches and one refinement cap → AC-2
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_first_candidate_passes_early_stopping` → passes and verifies depth first scheduling order with early stopping → AC-3
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_refinement_pass_recovers_failed_candidate` → passes and constructs refinement prompt to recover failed candidate → AC-4
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_unsafe_patch_rejected_and_skips_refinement` → passes and verifies patch safety rejection skips refinement → AC-5
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_fresh_sandbox_execution_and_cleanup_per_attempt` → passes and verifies fresh sandbox execution provisioning and cleanup → AC-6
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_budget_reservation_denial_halts_search` → passes and verifies cost reservation denial halts search immediately → AC-7
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_cancellation_during_branch_search` → passes and halts cleanly upon cooperative cancellation signal → AC-8
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_attempt_scoped_and_canonical_artifact_saving` → passes and saves attempt scoped and canonical winning artifacts → AC-9
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_multi_branch_exploration_after_refinement_failure` → passes and advances to candidate 2 after candidate 1 refinement fails → AC-10
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py -k test_build_refinement_prompt_structure` → passes and validates refinement prompt token and diff formatting → AC-11
- [x] `uv run --project backend pytest backend/tests/engine/test_branch_refine.py` → passes all 11 unit tests deterministically offline with zero external network calls → AC-12

## Acceptance-criteria coverage

- AC-1: covered by repair routes test
- AC-2: covered by exhaustion and tree caps test
- AC-3: covered by depth first scheduling and early stopping test
- AC-4: covered by refinement patch recovery test
- AC-5: covered by unsafe patch rejection test
- AC-6: covered by fresh sandbox execution isolation and cleanup test
- AC-7: covered by budget reservation denial test
- AC-8: covered by cancellation check test
- AC-9: covered by canonical and attempt artifact persistence test
- AC-10: covered by multi branch fallback exploration test
- AC-11: covered by refinement prompt structure test
- AC-12: covered by offline fake determinism full suite test
