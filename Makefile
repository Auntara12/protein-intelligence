.PHONY: dev test build lint migrate seed

# ── Local development ─────────────────────────────────────────────────────────

dev:
	@echo "Starting full stack with Docker Compose..."
	docker compose up --build

dev-backend:
	@echo "Starting backend only (requires Postgres + Redis running)..."
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	@echo "Starting frontend dev server..."
	cd frontend && npm run dev

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	@echo "Running all tests..."
	cd backend && PYTHONPATH=. python -m pytest tests/ -v --tb=short

test-unit:
	@echo "Running unit tests only (fast, no DB required)..."
	cd backend && PYTHONPATH=. python -m pytest tests/test_mutation_unit.py tests/test_alignment_unit.py -v

test-cov:
	@echo "Running tests with coverage report..."
	cd backend && PYTHONPATH=. python -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	@echo "Running Alembic migrations..."
	cd backend && alembic upgrade head

migrate-down:
	@echo "Rolling back one migration..."
	cd backend && alembic downgrade -1

migrate-history:
	cd backend && alembic history --verbose

# ── Build ─────────────────────────────────────────────────────────────────────

build:
	docker compose build

build-backend:
	docker build -t protein-intelligence-backend ./backend

build-frontend:
	cd frontend && npm run build

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	cd backend && python -m flake8 app/ --max-line-length=100 --exclude=__pycache__
	cd frontend && npm run lint

format:
	cd backend && python -m black app/ tests/
	cd frontend && npx prettier --write src/

# ── Shortcuts ─────────────────────────────────────────────────────────────────

logs:
	docker compose logs -f backend

shell-db:
	docker compose exec db psql -U postgres proteindb

shell-redis:
	docker compose exec redis redis-cli

health:
	curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
