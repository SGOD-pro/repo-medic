# RepoMedic

Automated dependency upgrade repair with cryptographic verification and test immutability proofs.

RepoMedic repairs codebases broken by major dependency upgrades. When an automated dependency bump tool breaks your test suite, RepoMedic analyzes the failure inside an isolated microcontainer sandbox, generates minimal source code patches using high parameter open models, and verifies that the patch passes all unchanged tests with zero test weakening.

Deployed Frontend: https://repo-medic-gamma.vercel.app  
Deployed Backend API: https://oflqusaa1e.execute-api.ap-south-1.amazonaws.com  
Demo Repository: https://github.com/SGOD-pro/repo-medic

---

## Why RepoMedic

Dependency upgrade bots notify you that a library is out of date, but major version bumps often break your codebase. Upgrading libraries like PyJWT, SQLAlchemy, Pydantic, or Click introduces API deprecations, type shifts, and altered runtime behaviors. Developers waste days triaging traceback logs and refactoring boilerplate.

RepoMedic automates this recovery safely:
1. **Isolated Execution**: Builds and runs your test suite inside containerized microcontainers.
2. **Targeted Repair**: Prompts high capability models with minimal diff context and execution tracebacks.
3. **AST Test Immutability**: Proves with Abstract Syntax Tree inspection that the patch only touches permitted source code and leaves your test suite completely intact.
4. **Target Version Verification**: Confirms that your test suite passes with the target dependency version installed, not the obsolete baseline.
5. **Signed Cryptographic Evidence**: Emits verifiable `patch.diff`, `verify.log`, and `evidence.json` files backed by SHA-256 hashes.

---

## System Architecture

RepoMedic is engineered as a distributed cloud system with strict separation between user interfaces, execution coordination, and secure worker sandboxes:

```
+-------------------------------------------------------------+
|                      RepoMedic UI                            |
|             Next.js 16 on Vercel Edge Network               |
|            https://repo-medic-gamma.vercel.app              |
+------------------------------+------------------------------+
                               |
                               | HTTPS / SSE
                               v
+-------------------------------------------------------------+
|                   Backend API & Gateway                     |
|           FastAPI + Mangum on AWS API Gateway               |
|               AWS Lambda Execution Runtime                  |
+--------------+-------------------------------+--------------+
               |                               |
               v                               v
+-----------------------------+ +-----------------------------+
|    Turso libSQL Database    | |   Worker Queue & Budget     |
| Micro-dollar budget ledger  | | Idempotent operation locks  |
| Durable runs and evidence   | | Per-run spend ceiling ($2)  |
+-----------------------------+ +-----------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                Isolated Repair Engine                       |
|           Nebius ConTree Microcontainer Sandboxes           |
|         Inference: nvidia/nemotron-3-super-120b-a12b        |
|             via Nebius Token Factory Endpoint               |
+-------------------------------------------------------------+
```

### Components

1. **Frontend**: Next.js 16 with React 19, Tailwind CSS 4, and Lucide React. Provides real time Server Sent Events streaming, interactive spatial visualizations, unified diff viewer, and instant access to verified production runs.
2. **Backend**: FastAPI with Mangum deployed on AWS API Gateway and AWS Lambda in `ap-south-1`. Coordinates run scheduling, budget reservations, and custom repository validations.
3. **Ledger**: Turso database powered by libSQL. Tracks every operation with micro dollar granularity, enforcing strict run level and global spend ceilings.
4. **Sandboxes**: Nebius ConTree microcontainers that spin up isolated Python execution runtimes for clean baseline checks, upgrade failure replication, and candidate verification.
5. **Model Inference**: Nebius Token Factory endpoint serving `nvidia/nemotron-3-super-120b-a12b`, generating precise, minimal source patches.

---

## Verified Production Runs

Judges can inspect real, retained production runs with verifiable diffs and evidence:

| Task ID | Library Upgrade | Incompatibility | Pinned SHA | Verified Run ID | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `TASK-DEMO-JWT` | `pyjwt==1.7.1` to `2.8.0` | `jwt.encode` returns str instead of bytes; decode call throws AttributeError | `8b635e7ff845` | `run_4c8b02996ca547a4a134e5ccaf682681` | Verified Clean |
| `TASK-DEMO-SHOP` | `sqlalchemy==1.4.46` to `2.0.25` | `session.query` syntax deprecated; 2.0 select syntax required | `69c3a3721340` | `run_a72af9a70dbc47ee9ba7c7b8b6ff1226` | Verified Clean |
| `TASK-DEMO-CLICK` | `click==7.1.2` to `8.1.7` | Parameter parsing and command callback signature changes | `69c3a3721340` | `run_f80b7c8b136f4e37ac27841d3067bc4b` | Verified Clean |
| `TASK-DEMO-PYDANTIC` | `pydantic==1.10.13` to `2.6.0` | `regex` field validator updated to `pattern` | `69c3a3721340` | `run_3b3ffafecdac4813a0f6120d6040d7eb` | Verified Clean |

You can open any verified run directly in your browser:
- Demo Auth JWT: `https://repo-medic-gamma.vercel.app/?runId=run_4c8b02996ca547a4a134e5ccaf682681`
- Demo Shop: `https://repo-medic-gamma.vercel.app/?runId=run_a72af9a70dbc47ee9ba7c7b8b6ff1226`

---

## Independent Reproduction

You do not have to take our word for it. You can independently reproduce the exact patch verification on a clean workstation.

### Step 1: Clone the Demo Repository at the Pinned SHA

```bash
git clone https://github.com/SGOD-pro/repo-medic.git repomedic-reproduce
cd repomedic-reproduce
git checkout 8b635e7ff84556962f6ec4fee43523778461c938
```

### Step 2: Observe the Upgrade Failure

```bash
uv venv .test_venv --python 3.12
source .test_venv/bin/activate
uv pip install "pytest>=8.0.0" "pyjwt==2.8.0"
pytest tests/
# Result: 3 tests fail with AttributeError: 'str' object has no attribute 'decode'
```

### Step 3: Fetch and Apply the Official Patch Artifact

Download `patch.diff` from the verified production run:

```bash
curl -sS https://oflqusaa1e.execute-api.ap-south-1.amazonaws.com/api/runs/run_4c8b02996ca547a4a134e5ccaf682681/artifacts/art_d4f48f4e3ca8 -o patch.diff
git apply patch.diff
```

### Step 4: Verify the Tests Pass

```bash
pytest tests/
# Result: 3 passed in 0.04s
```

All three token generation, claims verification, and token decoding tests pass cleanly without changing a single line of test code.

---

## Local Development and Testing

### Backend Unit Tests

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest tests/
```

### Frontend Unit and Typecheck Tests

```bash
cd frontend
npm install
npm run lint
npm run typecheck
npm run test
```

### End to End Browser Acceptance Test

The automated browser test exercises landing navigation, task selection, verification rendering, artifact download, and clean workstation test reproduction:

```bash
npx tsx frontend/tests/production_public_playwright.ts
```

---

## Security and Safety Gate

RepoMedic operates under a strict execution safety policy:
- **Test Immutability**: Any patch that alters test files, deletes assertions, or weakens verification thresholds is rejected immediately.
- **Microcontainer Isolation**: All code execution occurs inside single use, resource constrained containers without access to host resources or private credentials.
- **Budget Control**: The Turso database ledger enforces hard operation limits and transaction locks, preventing runaway loops or excessive compute spend.
- **Custom Repository Gate**: Custom repository execution on the public web tier requires administrative approval, preventing malicious payload execution or denial of service attempts on shared infrastructure.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
