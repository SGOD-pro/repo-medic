# Independent team build and integration

One repo / one frozen foundation BASE_SHA. Branches: feature/A-<task>, feature/B-<task>, feature/C-<task>, feature/D-<task>. One owner per package; foundation owns shared files. A/B/C use the same schema/config/install lock versions and local test instances.

Steps per task: read root + package AGENTS, current feature spec and relevant contract; write the named failing behavioral check; implement minimum owned changes; run targeted check then package/contracts suite; record evidence in docs/progress/<OWNER>.md; commit and prepare handoff. Don't rewrite adjacent modules to avoid a contract-change discussion.

Shared change request goes in docs/change-requests/<OWNER>-<task>.md: problem, proposed field/interface change, affected consumers, fixture update and migration/version impact. Lead resolves and merges shared contract first; all owners pull/regenerate before dependent work continues. Harmless local choices may be recorded without asking.

You may finish owned modules independently then assemble them as requested. Still run a minimal connection at foundation and scheduled offline contract integrations during development; no teammate must rely on another's unfinished implementation. Fakes isolate dependencies. Integration failures belong to the owner of the failed contract boundary, not whoever last merged.

Handoff packet: commit/BASE_SHA, owned paths, task statuses, exact tests/build commands and exits, fixtures used/provenance, pending limitations, contract changes (ideally none). Tests support claimed behavior; screenshots alone don't accept API/engine tasks.

Final merge order: foundation → B host/runtime boundaries → C engine/provider implementation → A frontend wiring → D evaluation tooling. A UI can merge earlier behind offline fixtures; this order describes integrated acceptance, not a requirement to keep all work unmerged. Each integration runs full offline tests before live checks. No merging an unimplemented real adapter that silently routes to fake output.

Three members: A/B/C. Lead performs D after integration, assisted by C metrics, B artifacts and A presentation. Fourth person: D tooling starts at F6, real results wait for live C. Keys only to lead/C designated operator; not every teammate.
