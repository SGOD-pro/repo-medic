# Review, main, 2026-10-18

**Reviewed by**: Gemini Pro (author on Gemini Flash)
**Scope**: 4 files, uncommitted
**Verdict**: Changes requested

## Summary
This change updates the Cloudflare Worker bridge authentication to fail closed when secrets are missing. It prevents requests from using default tokens unless explicit local flags are present, and stops hostname inspection from granting local access. The overall implementation is solid and well tested, but treating development environments as local creates a remote security risk that must be addressed before merge.

## Major
### 🟠 Remote development environment permits dummy token fallback, `db-worker/src/index.ts:24`
**Problem**: In `isExplicitLocal`, the condition checks whether `env.ENVIRONMENT === "development"` and treats it as an explicit local environment. Development is a common remote deployment environment name on Cloudflare Workers. When a worker is deployed to a remote development stage without `DB_BRIDGE_TOKEN` configured, it accepts `local-bridge-token` instead of returning HTTP 500 `auth_unconfigured`.
**Why it matters**: A remote development deployment accessible over the public internet will accept the known default token. Anyone can read or modify persistence data if the secret is missing. This violates requirement AC 3 of the governing spec, which requires fail closed authentication on remote deployments.
**Suggested fix**: Remove `env.ENVIRONMENT === "development"` from `isExplicitLocal`. Accept only `env.ENVIRONMENT === "local"` or explicit opt in via `ALLOW_LOCAL_DUMMY_TOKEN`.

## Minor
### 🟡 Bearer token compared with non constant time equality, `db-worker/src/index.ts:52`
**Problem**: Token validation checks `authHeader !== 'Bearer ${expectedToken}'` using standard string inequality. JavaScript engines exit early on the first differing character during string comparisons.
**Why it matters**: Comparing secrets without constant time behavior creates a side channel timing leak. Even though network variance across HTTPS makes practical attacks difficult, security standards recommend constant time comparison for authentication tokens.
**Suggested fix**: Compare authorization tokens using a constant time loop that checks length and accumulates character code differences before returning, or use a timing safe equality utility.

## Nits
- ⚪ `db-worker/src/index.ts:52`, Header validation enforces exact casing for "Bearer " rather than permitting standard case insensitive schemes.
- ⚪ `db-worker/test_worker.mjs:333`, Test coverage omits string values such as "1" for `ALLOW_LOCAL_DUMMY_TOKEN` and does not test precedence when both a custom secret and a dummy token flag are present.

## Strengths
- Fails closed with standard HTTP 500 `auth_unconfigured` when secrets are absent, empty, or whitespace.
- Proves in offline tests that request hostname values like localhost and 127.0.0.1 never bypass authentication.
- Preserves unauthenticated public access to the `/health` liveness probe.

## Test coverage
The offline test suite in `db-worker/test_worker.mjs` thoroughly tests the new authentication logic. It covers missing, empty, and whitespace secrets, header formatting errors, invalid tokens, trimmed secret comparison, and explicit local configuration flags. The main test gaps are the untested `ENVIRONMENT === "development"` branch and flag variations for `ALLOW_LOCAL_DUMMY_TOKEN`.
