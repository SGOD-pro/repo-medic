# Configuration and execution modes

Exact names: ../.env.example. Foundation implements one typed loader shared by API/worker/evaluation; browser only knows relative API paths and display provenance. Scripts must select offline without reading provider keys.

| Name group | Meaning |
|---|---|
| REPOMEDIC_MODE | offline / replay / live; process-selected, not client input |
| ALLOW_PAID_CALLS | false by default; true required alongside live config |
| NEBIUS_* | Server-only model credentials/base/confirmed NVIDIA model ID |
| SANDBOX_* | Server-only sandbox credentials/base/project if required; never assume same scopes |
| DATABASE_PATH / ARTIFACT_ROOT | Durable storage paths on one host, writable only by app |
| APP_ACCESS_CODE_HASH / JUDGE_ACCESS_CODE_HASH | Hashes of generated high-entropy codes; no plaintext config committed |
| MAX_ACTIVE_RUNS / MAX_PARALLEL_BRANCHES | Admission/execution limits, not provider limits |
| RUN_*LIMIT / RUN_DEADLINE_SECONDS | Run reservation caps including retries/diagnosis/refinement |
| RUN_COST_CAP_USD / LIVE_SPEND_CAP_USD | Estimated per-run/global ledger caps; unknown cost refuses paid admission |
| MODEL_*USD_PER_MILLION | Confirm actual billing basis; no invented prices |
| SANDBOX_BILLING_CONFIRMED | Mandatory before live execution; actual pricing/lifecycle captured separately |

Offline factory imports test support only in explicit dev/test entrypoints. Production package factory uses real engine code with fake adapters in offline mode, or real adapters in live mode; fake support modules never imported by live factory. Missing live config => unavailable, not fake. Replay serves frozen records and doesn't instantiate execution adapters.

Budget examples are operator policies, not enough evidence that a request costs $0.50. Initial model calls/output tokens low and serial. All test executions include two baseline checks, bump reproduction, candidate checks and fresh final verification. Minimum sequential example needs five test operations; account setup/install/forks/exports may have additional cost. Preserve final verification reserve. Sandbox time/storage/lifecycle charges require provider-specific accounting; if estimate cannot bound expense, stop live admission and run only operator-reviewed minimal probes.

Cookie Secure true in production HTTPS; loopback-only offline development may use Secure false. SameSite=Lax, HttpOnly, expiry/revocation; server checks Origin on mutations. Local dev proxy keeps browser/API same origin. No unbounded CORS wildcard with credentials.

Reject missing/invalid config at startup without revealing secrets. Secrets stay in operator's ignored .env or environment. Do not distribute real keys to A/B. Change paid limits via operator config + recorded experiment config; benchmark budgets stay fixed per arm after development tuning.
