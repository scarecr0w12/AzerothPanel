.PHONY: help install dev backend frontend lint check docker-up docker-down docker-build docker-logs docker-restart docker-quick

help:
	@echo "AzerothPanel – Available commands"
	@echo ""
	@echo "  make install        Install all dependencies (backend + frontend)"
	@echo "  make dev            Run backend + frontend in development mode"
	@echo "  make backend        Run only the FastAPI backend (port 8000)"
	@echo "  make frontend       Run only the Vite frontend (port 5173)"
	@echo "  make lint           Run TypeScript type-check on frontend"
	@echo ""
	@echo "  make docker-build   Build Docker images (no cache)"
	@echo "  make docker-quick   Build Docker images (with cache - much faster!)"
	@echo "  make docker-up      Build & start containers in background"
	@echo "  make docker-down    Stop and remove containers"
	@echo "  make docker-logs    Tail logs from all containers"
	@echo "  make docker-restart Rebuild & restart all containers"

# ─── Installation ─────────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	@echo "→ Installing Python dependencies…"
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt

install-frontend:
	@echo "→ Installing Node dependencies…"
	cd frontend && npm install

# ─── Development ──────────────────────────────────────────────────────────────

dev:
	@echo "→ Starting backend and frontend in parallel…"
	@make -j2 backend frontend

backend:
	@echo "→ Starting FastAPI backend on :8000"
	cd backend && \
	  [ -f .env ] || cp .env.example .env && \
	  [ -d .venv ] || python -m venv .venv && \
	  .venv/bin/pip install -r requirements.txt -q && \
	  .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	@echo "→ Starting Vite frontend on :5173"
	cd frontend && npm run dev

# ─── Quality ──────────────────────────────────────────────────────────────────

lint:
	cd frontend && npm run type-check 2>/dev/null || npx tsc --noEmit

check: lint
	@echo "✓ All checks passed"

# ─── Docker ───────────────────────────────────────────────────────────────────

# Enable BuildKit for all docker commands (required for cache mounts)
export DOCKER_BUILDKIT := 1
export COMPOSE_DOCKER_CLI_BUILD := 1

docker-build:
	@echo "→ Building Docker images (no cache)…"
	docker compose build --no-cache

docker-quick:
	@echo "→ Building Docker images (with cache - fast!)…"
	docker compose build

docker-up:
	@echo "→ Starting AzerothPanel in Docker…"
	[ -f .env ] || cp .env.example .env
	[ -f backend/.env ] || cp backend/.env.example backend/.env
	docker compose up --build -d
	@echo "✓ Panel is up → http://localhost:$$(grep -E '^PANEL_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 80)"

docker-down:
	@echo "→ Stopping containers…"
	docker compose down

docker-logs:
	docker compose logs -f

docker-restart:
	@echo "→ Rebuilding and restarting containers…"
	docker compose down
	docker compose up --build -d
	@echo "✓ Restarted → http://localhost:$$(grep -E '^PANEL_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 80)"

