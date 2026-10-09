# Canonical decisions v0.5

Status: design agreed in this conversation; application not implemented. Owner: foundation/integration lead. Effective authority: this document, executable contracts, current global docs, feature specs, then historical reference documents. On any contradiction stop the dependent task and request a correction; precedence does not authorize silent changes.

| Area | Frozen decision |
|---|---|
| Product | Repair pinned Python dependency upgrades, preserve pytest tests, export diff and evidence |
| Track | Coding and Agentic Engineering |
| Repo | One monorepo, three independently testable modules; optional evaluation package |
| Runtime | One HTTPS origin; static Next.js export, FastAPI API, one Python worker |
| Persistence | sqlite3 repository layer, SQLite WAL on durable local disk; private artifact directory |
| Live providers | NVIDIA Nemotron inference and Token Factory Sandboxes; account-confirmed endpoint/model/SDK binding |
| MVP scope | Public curated recipes; no arbitrary commands/repos, private repo access, auto PR/merge |
| App access | Access-code exchange, opaque hashed session token, cookie ownership checks |
| Shared contracts | Closed JSON Schema source, generated TS/OpenAPI, typed Python protocols |
| Event authority | API/host assigns run_id, seq and ts; atomically stores state/event; engine supplies EngineEvent |
| Engine storage | HostPorts only, no direct DB or HTTP dependency |
| Modes | offline/replay/live; server-selected; no automatic fallback or client-selected paid mode |
| Development | Package fakes first; first actual provider probe early; one live sequential repair before branching evaluations |
| Team | A UI, B API/storage/host, C engine/providers/verifier, optional D evaluation; lead owns shared foundation |
| Skills | JS Mastery shared context/scope; Superpowers inline task execution/TDD/debugging; no duplicate plan or auto subagent fanout |
| Payments | Approximate $25 total available; conservative internal reservations and manual actual billing reconciliation |
| Build dependencies | Python 3.12 / Node 22 chosen baselines. Foundation confirms availability and commits exact resolved lockfiles before team branching |

No vector DB, Redis/Celery, S3, OAuth, microservice networking or extra agent framework. Application hosting expense is separate unless confirmed included in available credits. Test scaffolding alone is not a functioning product.

Known unresolved facts and assigned owner:

- C+lead: actual model ID, inference/sandbox bases, keys/scopes, SDK version, checkpoint semantics, cancellation/cleanup, billing including reasoning and retained snapshots. Read current official docs/account; record evidence in FOUNDATION_RECORD.md.
- C: one real curated repository/commit/upgrade with twice-green baseline and reproducibly-red upgraded suite. Constructed fixtures in this kit do not satisfy this requirement.
- Lead+B: production host, durable volume, HTTPS, backup/restore, judge testing access and retention dates from official hackathon rules.
- Lead: exact app dependency pins/lockfiles and CI command record. No independent npm/pip latest installs after foundation freeze.

Model label mentioned by user is not validated. Smaller coding models may implement bounded tasks; security, recovery and verification still require human review and evidence.
