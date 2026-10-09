# RepoMedic — Evaluation protocol

Version 0.4 · 2026-10-09 · No benchmark results yet.

## 1. Questions

Does branch-and-refine improve accepted repairs versus sequential repair at comparable resources? Does refinement add value beyond independent candidates? If solve rate is similar, does parallel exploration reduce end-to-end latency enough to justify cost?

Do not treat a better animation, more inference calls or a larger model as evidence for the search algorithm.

## 2. Arms

| Arm | Definition | Purpose |
|---|---|---|
| A: single attempt | Shared diagnosis, one patch and same final verifier | Simple reference, intentionally lower budget |
| B: independent candidates | Candidates from same upgraded state, no failure-driven refinement; select with same gates | Sampling baseline |
| C: sequential repair | One trajectory, repeated patch/test feedback, no forks | Practical agent baseline |
| D: branch-and-refine | Distinct alternatives and failure-driven refinement | RepoMedic search strategy |

Do not describe A vs D as a compute-controlled comparison. Headline comparisons are D vs B and D vs C. Build C first; the product remains useful if D is not better.

## 3. Matched resources

Freeze comparable ceilings for B/C/D: aggregate input/output/reasoning tokens, estimated model spend and candidate/final test operations. Record actual consumption. A request count alone is not a fair budget. Charge shared diagnosis and optional review identically. Either fund final verification from each identical total or reserve the same explicit verification allowance for every arm.

Example initial experiment configuration (tune on development tasks only): three branches maximum, nine candidate test executions maximum, one reserved final verification, fixed token/spend ceiling determined after platform profiling. These are proposed settings, not provider quotas or measured optimal values.

Allow B to use its generation allocation, C to refine repeatedly and D to split/refine within the same totals. Invalid patches and retries consume budget. Use the same model/provider, context construction, references, protected verification and stopping rule. Compare parallel latency with documented concurrency; include sandbox time and costs so extra compute is visible.

## 4. Task acquisition and separation

Mine naturally occurring broken upgrades in public licensed Python repositories where possible; constructed bumps must be labeled. Pin repo SHA, exact versions, images and full resolved environments. Prefer multiple repositories and dependency families.

Record eligibility before repair attempts: reproducible baseline, reproducible post-bump failure, fast enough tests, supported environment and documented scope. Log every candidate and exclusion with reason. Do not choose final tasks because RepoMedic solved them.

Separate development/tuning tasks from held-out evaluation by repository where feasible. Freeze prompts/search policy before held-out runs. Keep known maintainer fix patches out of model context. Public training-data contamination cannot be ruled out; disclose it. Migration documentation is allowed only under an identical policy in every arm.

Aim for 15–20 tasks if affordable; smaller truthful data beats padded tasks. If many tasks share one repo, acknowledge correlated evidence. Synthetic tamper fixtures are a separate guard-test suite, not repair tasks contributing to solve rate.

## 5. Execution and reproducibility

Run each task/arm from an independent upgraded reference; rotate arm order to reduce provider-time effects. Record provider/model ID, parameters, prompt hash/version, tool versions, checkpoint IDs, environment hashes, tokens, operations, timings and application commit.

Use seeds where supported, but do not promise identical hosted-model outputs. Disable response-cache reuse across independent repetitions or disclose deterministic replay separately. Shared preparation cache is allowed only for identical pinned environments and equally available to arms.

Resuming skips only completed `(task, arm, config_hash, repetition)` records. A changed config never overwrites an earlier outcome. Include environment/provider failures in attempted counts and classify them separately; don't quietly rerun only failures until they pass. Set the retry policy in advance.

Where credits permit, repeat comparisons on a small prespecified subset; otherwise disclose one attempt per task/arm and stochastic uncertainty.

## 6. Reporting

Publish raw records plus a readable table:

| Arm | Accepted / eligible | Environment failures | Invalid/rejected patches | Model tokens | Estimated/actual spend | Sandbox time | Wall time | Human intervention |
|---|---|---|---|---|---|---|---|---|
| A | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| B | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| C | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| D | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Report paired task outcomes: D-only successes and C-only successes, and equivalent comparison with B. List all tasks and include failed examples. Total spend divided by accepted repairs includes spend on unsuccessful tasks; if zero accepted, report undefined, not zero cost.

Use raw counts for small datasets. Do not claim significance automatically or call every one-task difference “noise”: distinguish an observed difference from uncertainty about its generalization. No broad reliability percentage from curated tasks. Say “X of N tasks in our pinned evaluation.”

## 7. Outcome-to-pitch rules

- D improves accepted repairs at matched budgets: claim observed improvement on this dataset.
- Same acceptance, lower latency: claim measured speed tradeoff and report extra sandbox cost.
- No advantage: describe transparent verified repair and evidence; do not claim superior search.
- Invalid candidate accepted by integrity fixture: fix verifier before publicity.
- Maintainer rejects a green patch: preserve that feedback; tests are incomplete evidence.

## 8. First milestone

One pinned upgrade task, solved by sequential repair, verified freshly, with target version retained and a downloadable patch/report. Then compare branching. Do not spend the first week building a task miner and branch UI without this executable slice.
