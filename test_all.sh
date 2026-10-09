#!/bin/bash
set -e
echo "Running backend smoke tests..."
cd backend
uv run python smoke_test.py
cd ..
echo "Running frontend smoke tests..."
cd frontend
npm install --save-dev tsx typescript @types/node
npx tsx smoke_test.ts
cd ..
echo "All smoke tests passed."
