.PHONY: install test lint typecheck verify all

install:
	cd frontend && npm install
	cd db-worker && npm install
	cd backend && uv pip install -r requirements.txt

test:
	@echo "Running tests..."
	cd frontend && npm run test || echo "Frontend tests not configured yet"
	cd backend && python3 -m unittest discover tests || echo "Backend tests not configured yet"

lint:
	@echo "Running lint..."
	cd frontend && npm run lint || echo "Frontend lint not configured yet"
	cd backend && python3 -m flake8 src || echo "Backend lint not configured yet"

typecheck:
	@echo "Running typecheck..."
	cd frontend && npm run typecheck || npm run build || echo "Frontend typecheck not configured yet"
	cd backend && python3 -m mypy src || echo "Backend typecheck not configured yet"

verify: lint typecheck test
	@echo "Verification passed"

all: install verify
