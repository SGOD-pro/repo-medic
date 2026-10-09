# RepoMedic — User flow and demonstration video

Version 0.4 · 2026-10-09 · Proposed flow; capture only implemented behavior.

## 1. What users actually do

RepoMedic is a repair workbench. It does not replace Dependabot, edit the user's GitHub repository automatically or merge code.

### Public hackathon user

1. Open the site. Choose **Try a repair** or **Watch a recorded run**. Recorded examples are explicitly labeled and start without a login.
2. To start live work, enter the supplied access code. The app establishes a session; no signup or GitHub permissions.
3. Select a supported task card: repository, pinned commit, dependency before/after, expected setup and advertised limits. Do not imply a curated selection accepts any repository URL.
4. Click **Start repair**. Show queued/running status and a cancel control. Warn before work starts if live capacity or service access is unavailable.
5. The workbench displays baseline results, reproduced upgrade breakage, candidate strategies, test results and remaining budget.
6. Open a candidate to inspect diff and concise failure explanation. The user need not understand model routing or SDK details to evaluate it.
7. On success, show the installed target version, preserved-suite result, known limits and final patch. On failure, show exactly what remains broken and why execution stopped.
8. Download patch, readable evidence and JSON evidence. Refresh/reconnect preserves the live session's run.

### Developer with another repository

MVP path is local app/CLI with their own Token Factory credentials and a trusted recipe for a public repository. They specify pinned commit, install/test procedure and dependency upgrade. Extra setup failures are reported as unsupported environment, not misrepresented as repair failures.

Suggested CLI interface to implement, not an existing command:

```bash
repomedic repair --recipe recipes/my-project.json --mode branch_refine
```

Private repos and arbitrary hosted repository uploads are future scope. Clearly mark them unsupported.

### Applying the patch

The evidence identifies the exact expected commit. User checks out that commit in their own clone, makes a new branch, checks/applies the downloaded patch, installs the documented upgraded environment and runs the preserved suite. Show copyable recipe-specific commands only after verifying them. Users review code before merge.

The export bundle contains patch, baseline/upgraded/final summaries, actual dependency version/import origin, environment and protected hashes, branch lineage, usage/timing, application/model IDs and reproduction instructions. Do not claim this is a security certificate.

## 2. Screens

| Screen | Must communicate |
|---|---|
| Landing | Specific job, curated scope, live vs recorded choice |
| Task selection | Actual supported repo/commit/upgrade and limits |
| Workbench | Visible progress, strategies, budgets, cancellation |
| Candidate detail | Source diff and actual test outcomes |
| Final result | Fresh verification, target dependency, patch export, limitations |
| Evaluation | All arms, task count, matched budgets and paired outcomes |

The branch tree is an explanation tool. Keep the successful patch and evidence easy to find. Use “Recorded run — captured DATE” persistently during replay; never animate replay beneath a live label.

## 3. Judge access

Provide URL, judge code, one-click task instructions and functioning local/test-build setup in the submission. Do not require an email request, approval from the team, a paid subscription or undisclosed personal API keys for the hosted judging path.

Reserve sufficient credits to run the supported demo through Dec 15. General-public abuse protection must not impose restrictions that prevent the advertised judge workflow. If local setup needs credentials, disclose that and retain a working supplied judging route. Replay complements executable access.

## 4. Under-three-minute video storyboard

Target 2:45–2:55 to leave margin. Record an actual run; compress waiting honestly and display original elapsed time. No fabricated branches, fake tests or benchmark placeholders.

| Time | Screen/action | Suggested narration |
|---|---|---|
| 0:00–0:15 | Actual pinned upgrade and red CI/test output | “A dependency upgrade breaks this Python project's tests. RepoMedic produces a reviewable repair with verification evidence.” |
| 0:15–0:30 | Select task, inspect commit/upgrade, click Start | “This supported task runs on NVIDIA Nemotron through Nebius Token Factory, with execution in Token Factory Sandboxes.” |
| 0:30–1:05 | Baseline green, upgraded state red, strategies created | “We first reproduce the breakage. Each candidate starts from the same upgraded environment and tries a different repair.” |
| 1:05–1:30 | Inspect one failed candidate; show refinement if it really occurs | “Actual test failures guide the next edit. This alternative remains broken; this one progresses.” |
| 1:30–1:55 | Fresh verification, target version, test manifest | “The selected diff is reapplied in a fresh environment. The requested version remains installed, and the preserved suite completes without new skips or missing tests.” |
| 1:55–2:15 | Diff, evidence and download; brief local application check | “The maintainer receives the patch and reproduction instructions. RepoMedic does not merge it.” |
| 2:15–2:35 | Actual four-arm results with N and budgets | State only observed result: “On N pinned tasks, branching accepted X repairs versus Y sequential repairs under these budgets.” If no lift, state that. |
| 2:35–2:50 | Honest failure/limitations and usable URL | “Support is currently limited to these Python recipes. Passing tests is evidence, not a guarantee beyond their coverage. You can run the live example or inspect the recorded evidence.” |

Narration is draft copy; replace every result/model/service claim with what the captured build actually does. If the selected run does not refine, show a different genuine refinement example or omit that claim. An injected downgrade/tamper fixture can illustrate rejection only if visibly labeled as an injected guard test.

## 5. Recording procedure

- Pick a meaningful real upgrade requiring source repair, not simply downgrading the package or installing a missing tool.
- Verify task recipe and complete one rehearsal. Choose the hero example from the published dataset and disclose selection; don't present it as a random reliability sample.
- Capture at 1080p with readable text and cursor; hide access codes, API keys and account details.
- Start a fresh run. Record both browser and underlying evidence without editing outcomes.
- Show real service/model attribution from run metadata, not a pasted console badge.
- Speed up waits with an on-screen “accelerated; original runtime X” label. Keep genuine failures and transitions in correct order.
- Demonstrate downloads and, where time allows, patch application. Put full reproduction in README, not a long terminal montage.
- No third-party music/trademarks/assets without authorization. Upload publicly to YouTube and check runtime/link in an incognito window.

## 6. If the live service fails during recording

Do not fake the event stream. Fix service access or record a genuine local app run using Token Factory with its configuration clearly identified. Show replay as replay. Submission still needs a functioning judge test route. A polished video cannot substitute for implemented functionality.

## 7. What judges should be able to verify

Same pinned task/upgrade shown in metadata; real Nemotron calls; actual sandbox operation/checkpoint records; target version retained; full test collection/outcome evidence; exported patch matches the verified hash; results trace to published raw evaluation; failures are not hidden.

## 8. Product questions you must answer in the demo

“Why not one iterative coding agent?” — show matched-budget sequential comparison.

“Did you just give your agent more attempts?” — show budgets, actual consumption and independent-candidate baseline.

“Did you make green by changing tests or undoing the upgrade?” — show protected verification and installed target version.

“Can I use it?” — start a real supported run and download an actionable patch.

“What is new?” — describe measured repair/search behavior and transparent evidence, not invention of sandbox forks or test-running coding agents.
