# Turso Database Setup Guide

This guide describes how to configure a remote Turso libSQL database for RepoMedic deployment persistence.

## 1. Create a Turso Account

You can register via the web console or through the official command line interface.

### Web Console
1. Navigate to `https://turso.tech` in your browser.
2. Click `Sign Up` and authenticate using GitHub or your email.
3. Complete organization creation.

### Command Line Interface
If you prefer using the terminal:
```bash
# Install Turso CLI on Linux or macOS
curl -sSfL https://get.tur.so/install.sh | bash

# Authenticate with Turso
turso auth signup
# Or login if you already have an account
turso auth login
```

## 2. Create the Database

Create a new database instance named `repomedic-db` in your preferred geographical region:
```bash
turso db create repomedic-db
```

To list your available databases and inspect locations:
```bash
turso db list
```

## 3. Obtain Connection URL and Authentication Token

Retrieve the database URL and generate a secure authentication token. Keep this token strictly confidential. Never print it in build logs or commit it to version control.

### Obtain the Database URL
```bash
turso db show repomedic-db --url
```
The output format resembles:
```
libsql://repomedic-db-[your-org].turso.io
```

### Create an Authentication Token
```bash
turso db tokens create repomedic-db
```
The output is your JWT bearer token string. Store it safely in your local password manager.

## 4. Configure Backend Environment

In your `backend` directory, edit `.env` or export environment variables in your deployment environment:

```bash
# Select Turso as the active storage backend
REPOMEDIC_STORAGE_BACKEND=turso

# Remote Turso connection URL from step 3
TURSO_DATABASE_URL=libsql://repomedic-db-[your-org].turso.io

# Secure authentication token from step 3
TURSO_AUTH_TOKEN=your_auth_token_here
```

For local offline development without a remote Turso connection, you can omit `TURSO_AUTH_TOKEN` and point `TURSO_DATABASE_URL` to a local file such as `repomedic_local.db` or `:memory:`.

## 5. Verify Health and Initialize Schema

RepoMedic automatically applies idempotent schema migrations upon connection. You can verify health and schema readiness with the storage client utility:

```bash
cd backend
uv run python -m src.storage.turso_client health
```

Expected output:
```json
{"ok": true, "engine": "libsql", "status": "healthy"}
```

## 6. Execute Remote Persistence Acceptance

Once your credentials are configured, execute the dedicated acceptance test suite:

```bash
cd backend
TURSO_DATABASE_URL=libsql://repomedic-db-[your-org].turso.io \
TURSO_AUTH_TOKEN=your_token_here \
uv run pytest tests/test_k3_remote_turso.py -v
```

This validates:
1. Isolated test prefix execution without polluting existing data.
2. Atomic budget reservations and concurrent cap enforcement.
3. Durable run lifecycle and compare and swap transitions.
4. Process restart recovery of interrupted runs.
5. Exact cleanup of test manifests.
