This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## Browser Acceptance Testing

The repository includes a connected end to end browser acceptance test suite driving the real Next.js HTTP frontend, local Cloudflare D1 Worker bridge, and local FastAPI backend.

### Prerequisites

Start each service in a separate terminal before launching acceptance checks:

1. Local D1 Worker:
```bash
cd db-worker && npx wrangler dev --port 8787 --ip 127.0.0.1
```

2. Local Python Backend with offline repair engine:
```bash
cd backend && REPOMEDIC_USE_REAL_ENGINE=true REPOMEDIC_MODE=offline REPOMEDIC_WORKER_ENABLED=true REPOMEDIC_WORKER_POLL_INTERVAL_SECONDS=0.2 uv run uvicorn src.main:create_app --factory --host 127.0.0.1 --port 8000
```

3. Production Frontend HTTP Build:
```bash
cd frontend && NEXT_PUBLIC_API_TRANSPORT=http npm run build && npm run start -- -p 3000
```

### Running the Acceptance Suite

Run the full acceptance suite from the frontend directory:

```bash
npm run test:acceptance
```

### Environment Variables

The acceptance suite accepts the following optional environment variables:

- `BASE_URL`: Frontend URL (default: `http://localhost:3000`)
- `BACKEND_URL`: Python backend API URL (default: `http://127.0.0.1:8000`)
- `D1_WORKER_URL`: Cloudflare D1 Worker URL (default: `http://127.0.0.1:8787`)
- `ARTIFACT_DIR`: Directory where output screenshots and downloaded files are placed (default: `<repo-root>/artifacts`)
- `CHROMIUM_PATH`: Custom path to Chromium executable

