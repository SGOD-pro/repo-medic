# Spec 0010 Acceptance Report: Public GitHub Repository Repair

## 1. Executive Summary

This report documents the end to end user acceptance verification of public GitHub repository repair without user login for RepoMedic.

- **Deployed Frontend**: https://repo-medic-gamma.vercel.app (commit `d1ab5a4`, version V0.9.4)
- **Deployed Backend**: https://oflqusaa1e.execute-api.ap-south-1.amazonaws.com (AWS HTTP API Gateway with Lambda worker and Turso libSQL persistence)
- **Live Model Engine**: Nebius Token Factory Nemotron (`nvidia/nemotron-3-super-120b-a12b`)
- **Execution Sandbox**: ConTree container microVMs (`python:3.12-bookworm`)
- **Total Committed Budget**: $12.05 of $25.00 limit ($12.95 remaining headroom)
- **Dual Verdict**:
  - **Controlled Public Flow**: PASS. Real public repository intake, live branch discovery, commit pinning, rate limited dispatch, autonomous repair synthesis, container verification, and artifact downloads all succeed on both local and production environments.
  - **Unrestricted Code Execution Boundary**: GATED AND BOUNDED. ConTree microcontainers enforce ephemeral execution state and filesystem isolation, but lack network egress controls. Rate limits, concurrent execution caps, and command validation enforce bounded safety.

---

## 2. End to End Real User Flow Ledger

| Step | Operation | Local Environment Result | Production Environment Result | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **1. Branch Discovery** | Load public branches for `https://github.com/SGOD-pro/repo-medic.git` | Discovered 9 branches via `git ls-remote` | Discovered 9 branches via Git Smart HTTP advertisement (`/info/refs`) on AWS Lambda | Default branch `main` resolved with 9 public branches |
| **2. Commit Pinning** | Select branch `fixture/repomedic-demo-jwt` | Pinned commit `8b635e7ff84556962f6ec4fee43523778461c938` | Pinned commit `8b635e7ff84556962f6ec4fee43523778461c938` | Exact 40 character SHA verified against remote ref |
| **3. Intake Validation** | Validate package `pyjwt` 1.7.1 to 2.8.0 with tests `tests/` | Passed contract and regex safety checks | Passed contract and regex safety checks | Zero client errors, valid payload structure |
| **4. Run Creation** | Submit `POST /api/custom/run` | Generated run `run_36bece02c4ae4710b951292ae4477d3f` | Generated run `run_eec2cf25a30f46d49c7a4b75848d1052` | Task `TASK-CUSTOM-d031378d91a7fb457a7eab9fb1a38a3e`, HTTP 202 Accepted |
| **5. Queue Worker** | Dispatch through background worker | Local QueueWorker claimed run and prepared ConTree container | Production SQS Lambda worker claimed run and executed pipeline | Run transitioned from `queued` to `running` to `succeeded` |
| **6. Repair Synthesis** | Model generates minimal unified diff | Model synthesized 1 hunk fixing `raw.decode("utf-8")` | Model synthesized 1 hunk fixing `raw.decode("utf-8")` | 1 model call, 945 prompt tokens, 157 completion tokens |
| **7. Clean Verification** | Run unchanged tests against patched source | 3 of 3 tests passed in 15.9s | 3 of 3 tests passed in 8.3s | Zero new skips, test files unmodified |
| **8. Artifact Downloads** | Download `patch.diff`, `verify.log`, `evidence.json` | Hash verified: `cabdeedc...` | Hash verified: `cabdeedc...` | Identical patch diff hashes produced locally and on production |
| **9. Fresh Checkout Test** | Apply downloaded patch to clean checkout at pinned SHA | 3 passed with pyjwt 2.8.0; 3 failed without patch | Reversible regression verified independently | Independent test proof confirms patch validity |
| **10. UI Hydration** | Reload browser at `?runId=<id>` | Fully rehydrated cards and diff preview | Fully rehydrated cards, AST badge, and diff preview | State reloaded from Turso persistence |

---

## 3. Independent Reproduction and Verification Details

### Target Scenario: PyJWT 1.7.1 to 2.8.0 Upgrade
- **Public Repository**: `https://github.com/SGOD-pro/repo-medic.git`
- **Branch**: `fixture/repomedic-demo-jwt`
- **Pinned Commit SHA**: `8b635e7ff84556962f6ec4fee43523778461c938`
- **Dependency**: `pyjwt` 1.7.1 upgraded to 2.8.0
- **Test Command**: `pytest tests/`
- **Allowed Source Paths**: `src/auth/tokens.py`
- **Expected Failure**: `AttributeError: 'str' object has no attribute 'decode'`

### Clean Checkout Reproduction Proof
1. Cloned repository at pinned commit `8b635e7ff84556962f6ec4fee43523778461c938`.
2. Created clean Python 3.12 environment with `pyjwt==2.8.0` and `pytest`.
3. Executed baseline test command:
   ```
   tests/test_tokens.py FFF [100%]
   FAILED tests/test_tokens.py::test_generate_token - AttributeError: 'str' object has no attribute 'decode'
   FAILED tests/test_tokens.py::test_decode_token - AttributeError: 'str' object has no attribute 'decode'
   FAILED tests/test_tokens.py::test_verify_claims - AttributeError: 'str' object has no attribute 'decode'
   3 failed in 0.03s
   ```
4. Applied the exact production downloaded patch `/tmp/prod_patch.diff`:
   ```diff
   diff --git a/src/auth/tokens.py b/src/auth/tokens.py
   index d90d786..646e99d 100644
   --- a/src/auth/tokens.py
   +++ b/src/auth/tokens.py
   @@ -2,8 +2,7 @@ import jwt
    
    def generate_token(user_id: str, role: str, secret: str, algorithm: str = "HS256") -> str:
        payload = {"sub": user_id, "role": role}
   -    raw = jwt.encode(payload, secret, algorithm=algorithm)
   -    return raw.decode("utf-8")
   +    return jwt.encode(payload, secret, algorithm=algorithm)
    
    def decode_token(token: str, secret: str, algorithms: list = None) -> dict:
        if algorithms is None:
   ```
5. Re-ran test command without altering any test code:
   ```
   tests/test_tokens.py ... [100%]
   3 passed in 0.04s
   ```
   Result: 100% verified resolution with zero modifications to test files.

---

## 4. Run Identifiers and Artifact Ledger

### Production Run Evidence
- **Run ID**: `run_eec2cf25a30f46d49c7a4b75848d1052`
- **Task ID**: `TASK-CUSTOM-d031378d91a7fb457a7eab9fb1a38a3e`
- **State**: `succeeded`
- **Verification Duration**: 8.3 seconds
- **Model Usage**: 1 call, 945 input tokens, 157 output tokens ($0.35 estimated spend ceiling, $0.05 settled spend)
- **Artifacts**:
  - `patch.diff` (ID `art_9903888d0a2e`): SHA 256 `cabdeedcd67cf051aae35c7a39b6e8a377cdf5e483c4ea0b44abf96750a2cdf6`
  - `verify.log` (ID `art_62a04856e33f`): SHA 256 `eaacc639baaeee87472cacdd52acc23e6819f7aa592e17b335b9f17985519075`
  - `evidence.json` (ID `art_6e27fcf53706`): SHA 256 `a576de8abebf4e7c8bc320dce5af1f437afa06e359188e11c8ccde2213b176cf`

### Local Run Evidence
- **Run ID**: `run_36bece02c4ae4710b951292ae4477d3f`
- **Task ID**: `TASK-CUSTOM-d031378d91a7fb457a7eab9fb1a38a3e`
- **State**: `succeeded`
- **Verification Duration**: 15.9 seconds
- **Artifacts**:
  - `patch.diff` (ID `art_60ea94d71292`): SHA 256 `cabdeedcd67cf051aae35c7a39b6e8a377cdf5e483c4ea0b44abf96750a2cdf6`
  - `verify.log` (ID `art_5b82b2680358`): SHA 256 `eaacc639baaeee87472cacdd52acc23e6819f7aa592e17b335b9f17985519075`
  - `evidence.json` (ID `art_a15a3ac09a73`): SHA 256 `aca678a9ddab84163795d1ec1e35dfa1883ffb650b2623651d47172488fe6d74`

---

## 5. Architectural Improvements Made During Implementation

1. **Git Smart HTTP Native Resolver**:
   AWS Lambda standard execution environments lack the `/usr/bin/git` binary. The resolver was enhanced with an unauthenticated Git Smart HTTP advertisement fallback (`/info/refs?service=git-upload-pack`). This provides branch discovery and commit pinning in 200 milliseconds without GitHub REST API rate limit exhaustion and without requiring external binaries.
2. **Artifact Identification Ergonomics**:
   The `/api/runs/{id}/artifacts/{artifact_id}` endpoint was enhanced to accept artifact IDs, kinds (`patch`, `log`, `evidence`), or filenames (`patch.diff`, `verify.log`, `evidence.json`), ensuring seamless CLI downloads.
3. **Deterministic Task Identifier**:
   Custom tasks generate stable SHA 256 derived identifiers (`TASK-CUSTOM-<hash>`) based on the repository URL, commit SHA, and dependency configuration, preventing duplicate task records during idempotent retries.
4. **Enforceable Abuse Controls**:
   Implemented database backed rate limiting buckets:
   - 10 branch resolution requests per minute per client IP
   - 3 custom repair requests per 10 minutes per repository URL
   - Maximum 2 concurrent active custom runs across the system
   - $0.50 budget reservation ceiling per run with atomic ledger accounting
