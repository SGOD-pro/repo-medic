# Frontend (Package A)

## Overview

Package A provides the user interface for RepoMedic built with Next.js App Router and React. It displays task progression, event streams, run history, and verification outputs.

## Key files

| File | Owns |
|---|---|
| `src/app/page.tsx` | Main dashboard and run interface |
| `src/app/layout.tsx` | Root HTML layout and font setup |
| `src/lib/contracts.ts` | TypeScript contracts mirroring backend domain models |
| `src/lib/validation.ts` | Runtime schema validation helpers |
| `smoke_test.ts` | Smoke test runner for frontend validation |

## Commands

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build production bundle
npm run build

# Run linter
npm run lint

# Run type checks
npm run typecheck

# Run smoke tests
npm run test
```

## Conventions

* Next.js 16 with App Router and Turbopack
* React 19 server and client components
* Styling using Tailwind CSS v4
* Respect package boundaries, Package A owns frontend UI and checks

## Gotchas

* Contract types in `src/lib/contracts.ts` must stay synchronized with backend contracts

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
