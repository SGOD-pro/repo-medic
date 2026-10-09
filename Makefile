.PHONY: install test lint typecheck verify all

install:
	cd frontend && npm install
	cd db-worker && npm install
	cd backend && uv sync

test:
	@echo "Running tests..."
	cd frontend && npm run test
	cd backend && uv run pytest

lint:
	@echo "Running lint..."
	cd frontend && npm run lint
	cd backend && uv run python3 -m flake8 src tests

typecheck:
	@echo "Running typecheck..."
	cd frontend && npm run typecheck
	cd backend && uv run python3 -m mypy src tests

verify: lint typecheck test
	@echo "Verification passed"

all: install verify
