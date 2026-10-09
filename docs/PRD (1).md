# Product requirements v0.5

Primary user: a Python maintainer evaluating a dependency upgrade. MVP offers curated public recipes, not uploads or arbitrary repository execution.

## Acceptance criteria

1. Landing page clearly distinguishes live execution, synthetic offline example and recorded replay.
2. Access-code session permits starting a curated run. Invalid/expired sessions and quotas have understandable errors.
3. User can see the dependency versions, run status, meaningful candidate history and budget usage. No fabricated percent-complete.
4. Live run demonstrates twice-green baseline, red requested upgrade, candidate patch search and fresh verification.
5. A candidate cannot become success when protected files/version/import provenance/collection/skips/full-suite gates fail.
6. Cancellation stops scheduling new work; late completed remote operations cannot turn a cancelled run into success.
7. A successful result exposes a diff and evidence; failures expose diagnostics with no success badge/winner.
8. SSE disconnect/reconnect recovers from persisted events without duplicate branch nodes. Refresh rebuilds the view from summary.
9. Artifacts are session-owned, safely addressed by artifact ID and integrity checked. No browser/provider credentials.
10. Evaluation states methodology, denominators, costs and limitations; unrun evaluation stays `not_run`.

No chat-only demo, private GitHub auth, auto merge, app signup, arbitrary shell commands or simulated live success. CLI/evaluation may use operator-reviewed additional public recipes after all checks; public app stays curated.

Feature-level requirements and test names live in docs/specs/ through the work packages. This file defines product behavior; schemas define exact transport fields.
