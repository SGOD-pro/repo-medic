# Production Deployment Guide

This guide describes how to deploy RepoMedic in production using AWS Serverless Application Model (AWS SAM) and Vercel, with remote Turso database persistence and live cloud providers.

## Architecture Overview

RepoMedic separates frontend presentation from background repair execution across two cloud platforms:

1. **Frontend on Vercel**: Next.js web application deployed on Vercel with server side rendering, static asset caching, and strict cross origin request protection.
2. **Backend on AWS SAM**: Decoupled serverless infrastructure defined in `backend/template.yaml`:
   * **API Lambda (`RepoMedicApiFunction`)**: Handles synchronous HTTP requests via API Gateway HTTP API or Lambda Function URL. It creates runs in Turso and enqueues messages to Amazon SQS.
   * **Amazon SQS (`RepoMedicRepairQueue`)**: Reliable message queue buffering repair jobs with a 960 second visibility timeout and dead letter queue redrive (`RepoMedicRepairDLQ`) after 3 failed attempts.
   * **Worker Lambda (`RepoMedicWorkerFunction`)**: Asynchronous execution function invoked by SQS with batch size 1 and a 900 second timeout. It claims the run atomically via Compare And Swap, runs the repair pipeline against live providers, and saves artifacts.
3. **Database on Turso**: Remote libSQL database hosted on Turso (`libsql://repo-medic-swyra-07.aws-ap-south-1.turso.io`) storing task definitions, runs, events, usage, and artifacts.
4. **Model and Sandbox Providers**: Nebius Token Factory (`nvidia/nemotron-3-super-120b-a12b`) for inference and ConTree microcontainers (`python:3.12-bookworm`) for isolated sandbox execution.

## Local and Standalone Parity

The existing single process architecture remains fully supported. In local development or standalone container hosts, FastAPI and the embedded `QueueWorker` run together in one process.

When deploying to AWS Lambda, setting `REPOMEDIC_WORKER_ENABLED=false` and `REPOMEDIC_STARTUP_RECOVERY_ENABLED=false` ensures API Lambda instances never execute poll loops or mark active background jobs as failed during cold starts.

## AWS SAM Backend Deployment

### Prerequisites

* AWS CLI and AWS SAM CLI installed.
* Docker installed (for `sam build --use-container` with native libSQL extensions).
* AWS account with permissions for CloudFormation, IAM, Lambda, SQS, and API Gateway.
* Turso database URL and auth token.
* Nebius Token Factory and ConTree API credentials.

### Build and Validate Commands

Run these commands inside the `backend` directory:

```bash
cd backend

# Export frozen backend dependencies to requirements.txt
uv export --no-dev --no-hashes -o requirements.txt

# Validate the SAM template
sam validate --lint

# Build container packages matching Lambda Amazon Linux 2023 x86_64
sam build --use-container
```

### Deployment Command

Deploy the serverless stack from the `backend` directory using `sam deploy`:

```bash
cd backend

sam deploy \
  --stack-name repomedic-production \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    Environment=production \
    AppOrigin=https://repo-medic.vercel.app \
    TursoDatabaseUrl=libsql://repo-medic-swyra-07.aws-ap-south-1.turso.io \
    TursoAuthToken="<YOUR_TURSO_AUTH_TOKEN>" \
    NebiusApiKey="<YOUR_NEBIUS_API_KEY>" \
    NebiusProjectId="<YOUR_NEBIUS_PROJECT_ID>" \
    RepairMode=live \
    UseRealEngine="true"
```

### Outputs

After deployment completes, CloudFormation exports these endpoints:

* `FunctionUrlEndpoint`: Direct Lambda Function URL with streaming capability.
* `HttpApiEndpoint`: AWS API Gateway HTTP API endpoint URL.
* `RepairQueueUrl`: Amazon SQS repair queue URL.
* `RepairDLQArn`: Amazon SQS dead letter queue ARN.

## Vercel Frontend Deployment

Deploy the Next.js frontend to Vercel:

1. **Link Repository**: In the Vercel dashboard, import the repository `SGOD-pro/repo-medic`.
2. **Project Settings**:
   * Root Directory: `frontend`
   * Framework Preset: Next.js
   * Node.js Version: 22.x
   * Build Command: `npm run build`
3. **Environment Variables**:
   * `NEXT_PUBLIC_API_TRANSPORT`: `http`
   * `NEXT_PUBLIC_API_URL`: `/api`
   * `BACKEND_URL`: Value of `HttpApiEndpoint` or `FunctionUrlEndpoint` (without trailing slash)
   * `NEXT_PUBLIC_DOCS_URL`: `https://github.com/SGOD-pro/repo-medic`

## Security, CORS, and Budget Policies

1. **Strict CORS Policy**: Cross origin access is restricted to domains specified in `AppOrigin` (for example `https://repo-medic.vercel.app`) plus local development origins (`http://localhost:3000`). Wildcard patterns matching all Vercel sites are strictly forbidden.
2. **Server Controlled Budgets**: Global spending limits are enforced on the server (`repomedic_total_budget_usd = 25.0`, `repomedic_max_run_usd = 2.0`). Client requests cannot modify spending caps.
3. **Disabled Internal Endpoints**: The internal reservation route `POST /api/runs/{id}/operations` is disabled in production and returns HTTP 404.
4. **Least Privilege IAM**: The API Lambda is granted permissions only to send messages to `RepoMedicRepairQueue`. The Worker Lambda is granted SQS execution and receive permissions for `RepoMedicRepairQueue`.

## Safe Demonstration Path for Judges

Judges evaluating RepoMedic can inspect the complete verified repair results without initiating paid cloud runs or depleting live budgets:

1. **One Click Demo Banner**: A prominent banner at the top of the tasks dashboard highlights `TASK-091` (`run_93c660238e3443a6a18249167eb1939b`). Clicking View Validated Results navigates directly to the verification report.
2. **Direct URL Hydration**: Visiting `/?runId=run_93c660238e3443a6a18249167eb1939b` instantly hydrates the complete run from remote Turso storage.
3. **Evidence Inspection**: The verification view displays 1/1 tests passing, 0 regressions, post patch test unchanged proof badges, unified change diff for `src/backend/database.py`, and download buttons for `patch.diff`, `verify.log`, and `evidence.json`.
4. **Independent Verification**: The downloaded patch can be applied using `git apply --recount --whitespace=nowarn` against pinned commit `453a0b6c6b125177504cdd941902b8d48266ed1c` on `https://github.com/SGOD-pro/repo-medic.git` and passes pytest with exit code 0.

## Post Deployment Verification Procedure

Once deployed, run this checklist against the public production environment:

1. **Public Health and Task Discovery**:
   ```bash
   curl -s https://[api-endpoint]/api/tasks | grep "TASK-091"
   ```
   Confirm tasks return with HTTP 200.

2. **Budget Usage Endpoint**:
   ```bash
   curl -s https://[api-endpoint]/api/budget/usage
   ```
   Confirm committed and reserved amounts remain within the $25.00 limit.

3. **Public Frontend and Demo Hydration**:
   Open `https://[frontend-domain]/?runId=run_93c660238e3443a6a18249167eb1939b` in a browser. Confirm that the verification report loads from remote Turso without starting a new run.

4. **Artifact Downloads**:
   Download `patch.diff`, `verify.log`, and `evidence.json` directly from the web interface. Confirm SHA-256 hashes match stored metadata.

5. **Live Bounded Repair**:
   Select `TASK-091` in the UI and click Start with Sequential search. Verify that SQS receives the message, the worker Lambda executes the repair, and the browser reaches `succeeded` status within the $2.00 cap.

6. **Patch Reproduction**:
   Clone pinned commit `453a0b6c6b125177504cdd941902b8d48266ed1c`, apply the downloaded `patch.diff`, install `sqlalchemy==2.0.19`, and verify tests pass 1/1.

## Secret Management and IAM Policy

AWS secret store migration is currently blocked by IAM permissions. The operator identity `arn:aws:iam::445567096027:user/personal_dev` returned `AccessDeniedException` when querying `secretsmanager:ListSecrets` and `ssm:DescribeParameters`. Consequently, automated migration to AWS Secrets Manager or Systems Manager Parameter Store cannot be completed until an account administrator attaches the required policy. Secret parameters remain secured via CloudFormation parameter retention without exposing plaintext keys in CLI arguments or shell history.

### Administrator Least Privilege IAM Policy

An administrator should attach the following policy to enable secret store integration for the deployment user and Lambda execution roles:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RepoMedicSecretStoreAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:CreateSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:ap-south-1:445567096027:secret:repomedic/*"
      ]
    },
    {
      "Sid": "RepoMedicSSMParameterAccess",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:PutParameter",
        "ssm:DescribeParameters"
      ],
      "Resource": [
        "arn:aws:ssm:ap-south-1:445567096027:parameter/repomedic/*"
      ]
    }
  ]
}
```

### Credential Rotation Procedure

When rotating `TURSO_AUTH_TOKEN` or `NEBIUS_API_KEY`:

1. Generate new credentials in the respective provider console (Turso CLI or Nebius console).
2. Validate new credentials locally using isolated curl probes before updating production.
3. Update CloudFormation parameter values using secure environment variable inputs or deploy scripts that omit command arguments.
4. Verify API and Worker Lambda functions can authenticate by invoking `/health` and checking CloudWatch logs.
5. Invalidate and revoke the old tokens in the provider console once the new deployment is healthy.
