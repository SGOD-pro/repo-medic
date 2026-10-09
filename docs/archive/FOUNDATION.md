# Foundation setup — lead + C

Do this before distributing the repository to teammates. Each numbered F task has a corresponding feature spec.

- F0: Copy kit into one repo. Run supplied checks. Select Python 3.12 and Node 22; confirm all machines. Record source pins/contract version. No provider calls.
- F1: Freeze shared schema, interfaces, SQL and ownership. Read generated types/OpenAPI with A/B/C. Correct any omissions before branching. Run schema/negative tests. No provider calls.
- F2: Scaffold real Next.js static app and importable API/repair/evaluation/shared-contract Python packages. Commit lockfiles and install scripts. API DB wrapper uses sqlite3, API models use Pydantic at the boundary and must pass canonical JSON Schema fixtures. Use pytest for Python feature tests, Vitest for UI unit tests, Playwright for browser acceptance. Pin resolved package versions once. No real SDK imports needed in offline test path.
- F3: Implement one shared config loader/production factory. Offline refuses remote requests; live requires explicit flags/config. Local session cookie exception only on loopback dev. Add offline package test commands to CI. No provider calls.
- F4: Build tiny actual frontend/API/fake-engine connection: exchange offline code, list task, start run, receive SSE, reach terminal summary and download the synthetic patch. Clearly labeled offline. This is a wiring check, not completing A/B/C features.
- F5: C+lead inspect official account/docs and perform one tiny model call plus minimal sandbox operation, tracking usage/resources. Stop at ~$2 planned spike allocation or configured limits. Missing sandbox access blocks live adapters, not offline package work. Capture sanitized contract-shaped fixtures and FOUNDATION_RECORD evidence. No keys in repo.
- F6: Freeze BASE_SHA, commands, locks, contract checksum and task ownership. Distribute repo + A/B/C entrypoint docs. Branch from BASE_SHA, never separate scaffolds.

Do not select a live task from the supplied toy example. A real task requires repo URL/commit, dependency snapshots, image/Python/runner/plugin versions, reproducible baseline/upgrade and approved paths. SDK binding remains pending until documented/tested; typed protocols do not validate cloud semantics.

A can start mock design after F1, but implementation handoff is F6. B/C may assist foundation in separate scoped tasks coordinated by lead. One person owns shared file merges.
