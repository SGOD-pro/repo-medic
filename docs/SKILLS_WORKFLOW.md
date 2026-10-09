# Skills mapping and agent execution

Sources checked at these commits (pin for reproducibility; don't auto-upgrade mid-build):

- JS Mastery: https://github.com/jsmastery-pro/skills/tree/43b69e44c9ca905fe3a3418ccdf4102255e20d40
- Superpowers: https://github.com/obra/superpowers/tree/8ca22dba9a94f28898bbce59f2537ff4d87c747d
- JS workflow guide: https://github.com/jsmastery-pro/skills/blob/43b69e44c9ca905fe3a3418ccdf4102255e20d40/docs/workflow-guide.md
- Superpowers task plans: https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/writing-plans/SKILL.md
- Inline execution: https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/executing-plans/SKILL.md

Both are development instructions, not RepoMedic runtime libraries or cheaper inference providers. User configures/install skills in Antigravity. Foundation records actual installed revision and how agents load AGENTS.md; not all tools automatically read that filename. If necessary explicitly attach root/package instructions at session start. Don't silently copy full third-party repositories into this kit or assume installation complete.

| Stage | Skills to use | Scope |
|---|---|---|
| Foundation scope | JS `scope`, `architect` only for unresolved decisions | Existing product/stack is frozen; no new brainstorm/rearchitecture |
| Scaffold/context | JS `audit` | Root/package AGENTS from actual scaffold; preserve kit constraints |
| Package task planning | Superpowers `writing-plans` | Already supplied feature specs; expand only current task, exact paths/checks |
| Build each feature | Superpowers `executing-plans`, `test-driven-development` | Inline implementation and red→green check; no automatic subagent fanout |
| Failure | Superpowers `systematic-debugging` | Evidence, reproduction, regression then minimal fix |
| Completion | Superpowers `verification-before-completion`; JS `check verify` where useful | Actual code/application checks, not replay mistaken for live proof |
| Handoff | JS `document`, `sync`; Superpowers branch finishing | PR/evidence/context; never rewrite frozen contracts during sync |
| Critical review | JS `check review` or human review | B auth/recovery and C verifier/providers; one review of coherent change, not every tiny task |

Project-specific overrides authorized by this user: no automatic assumption/ruling may alter a shared interface, DB, provider, security boundary or paid budget. Record a change request to lead instead. Superpowers' inline local rulings are permitted only within existing contracts/owned paths. Don't run duplicate JS `develop/test/debug` and Superpowers execution/TDD/debug loops for the same task; use the mapping above. Skills' extra planning paths should point to docs/specs and this kit's ledgers rather than create competing sources of truth.

For low-cost coding agents: one task per prompt; include only START_HERE/root rules + package brief + current spec + selected schemas/fixtures. Don't paste all historical docs/logs. Write ledger after every task, start a fresh session at feature boundary, read ledger on resume. Use deterministic tools for tests/config/diff checks. Escalate ambiguity/security bugs rather than spending repeated prompts inventing interfaces. No model name or capability is assumed.
