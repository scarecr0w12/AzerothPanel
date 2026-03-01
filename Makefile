.PHONY: help install dev backend frontend lint check docker-up docker-down docker-build docker-logs docker-restart docker-quick daemon-start daemon-stop daemon-restart daemon-status daemon-install update version

help:
	@echo "AzerothPanel – Available commands"
	@echo ""
	@echo "  make install           Install all dependencies (backend + frontend)"
	@echo "  make dev               Run backend + frontend in development mode"
	@echo "  make backend           Run only the FastAPI backend (port 8000)"
	@echo "  make frontend          Run only the Vite frontend (port 5173)"
	@echo "  make lint              Run TypeScript type-check on frontend"
	@echo ""
	@echo "  make docker-build      Build Docker images (no cache)"
	@echo "  make docker-quick      Build Docker images (with cache - much faster!)"
	@echo "  make docker-up         Build & start containers in background"
	@echo "  make docker-down       Stop and remove containers"
	@echo "  make docker-logs       Tail logs from all containers"
	@echo "  make docker-restart    Rebuild & restart all containers"
	@echo ""
	@echo "  Update commands:"
	@echo "  make version           Show current version and commits behind origin"
	@echo "  make update            Pull latest code from GitHub & rebuild containers"
	@echo ""
	@echo "  Host Process Daemon (run ONCE on the host machine):"
	@echo "  make daemon-start      Start the AC host daemon in the background"
	@echo "  make daemon-stop       Stop the AC host daemon"
	@echo "  make daemon-restart    Restart the AC host daemon"
	@echo "  make daemon-status     Show daemon status and managed processes"
	@echo "  make daemon-install    Install daemon as a systemd service (recommended)"

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

# ─── Update ───────────────────────────────────────────────────────────────────

version:
	@echo "→ AzerothPanel version info"
	@git describe --tags --always 2>/dev/null || git rev-parse --short HEAD
	@echo "  Branch: $$(git rev-parse --abbrev-ref HEAD)"
	@echo "  Commit: $$(git rev-parse --short HEAD)"
	@git fetch --quiet --tags 2>/dev/null; \
	  BEHIND=$$(git rev-list --count HEAD..origin/HEAD 2>/dev/null || echo "?"); \
	  if [ "$$BEHIND" = "0" ]; then echo "  Status: Up to date"; \
	  else echo "  Status: $$BEHIND commit(s) behind origin"; fi

update:
	@echo "→ Pulling latest AzerothPanel from GitHub…"
	git pull --rebase
	@echo "→ Rebuilding and restarting containers…"
	docker compose up --build -d
	@echo "✓ AzerothPanel updated → http://localhost:$$(grep -E '^PANEL_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 80)"

# ─── Host Process Daemon ──────────────────────────────────────────────────────
# The daemon runs ON THE HOST (not inside Docker) so that worldserver and
# authserver are owned by the host cgroup and survive Docker container restarts.
#
# Quick start:
#   make daemon-start
#
# For auto-start on boot (recommended):
#   make daemon-install   (installs a systemd service)

DAEMON_HOST ?= 127.0.0.1
DAEMON_PORT ?= 7879
DAEMON_PIDFILE ?= /tmp/azerothpanel-daemon.pid
DAEMON_LOG ?= /var/log/azerothpanel-daemon.log
# Use the backend virtualenv's Python (it already has psutil); fall back to system python3.
PYTHON ?= $(shell [ -x backend/.venv/bin/python3 ] && echo backend/.venv/bin/python3 || which python3)

daemon-start:
	@echo "→ Starting AC host daemon…"
	@if [ -f $(DAEMON_PIDFILE) ] && kill -0 $$(cat $(DAEMON_PIDFILE)) 2>/dev/null; then \
		echo "  Daemon already running (PID $$(cat $(DAEMON_PIDFILE)))"; \
	else \
		nohup $(PYTHON) backend/ac_host_daemon.py --host $(DAEMON_HOST) --port $(DAEMON_PORT) \
			>> $(DAEMON_LOG) 2>&1 & \
		echo $$! > $(DAEMON_PIDFILE); \
		sleep 1; \
		echo "  Daemon started (PID $$(cat $(DAEMON_PIDFILE)))"; \
		echo "  Listening: $(DAEMON_HOST):$(DAEMON_PORT)"; \
		echo "  Log:    $(DAEMON_LOG)"; \
	fi

daemon-stop:
	@echo "→ Stopping AC host daemon…"
	@if [ -f $(DAEMON_PIDFILE) ] && kill -0 $$(cat $(DAEMON_PIDFILE)) 2>/dev/null; then \
		kill $$(cat $(DAEMON_PIDFILE)); \
		rm -f $(DAEMON_PIDFILE); \
		echo "  Daemon stopped"; \
	else \
		echo "  Daemon is not running"; \
		rm -f $(DAEMON_PIDFILE); \
	fi

daemon-restart: daemon-stop
	@sleep 1
	@$(MAKE) daemon-start

daemon-status:
	@if [ -f $(DAEMON_PIDFILE) ] && kill -0 $$(cat $(DAEMON_PIDFILE)) 2>/dev/null; then \
		echo "  Daemon running (PID $$(cat $(DAEMON_PIDFILE)))"; \
	else \
		echo "  Daemon is NOT running"; \
	fi
	@echo "{\"cmd\":\"list\"}" | $(PYTHON) -c \
		"import socket,sys,json; s=socket.socket(); s.connect(('$(DAEMON_HOST)',$(DAEMON_PORT))); s.sendall(sys.stdin.buffer.read()); print(json.dumps(json.loads(s.recv(4096)),indent=2)); s.close()" \
		2>/dev/null || echo "  (daemon not reachable on $(DAEMON_HOST):$(DAEMON_PORT))"

daemon-install:
	@echo "→ Installing azerothpanel-daemon systemd service…"
	@cp backend/azerothpanel-daemon.service /tmp/ac-daemon-install.service
	@sed -i "s|__PANEL_DIR__|$(PWD)|g" /tmp/ac-daemon-install.service
	@cp /tmp/ac-daemon-install.service /etc/systemd/system/azerothpanel-daemon.service
	@rm -f /tmp/ac-daemon-install.service
	@systemctl daemon-reload
	@systemctl enable azerothpanel-daemon
	@systemctl start azerothpanel-daemon
	@echo "✓ Daemon installed and started via systemd"
	@echo "  Check status: systemctl status azerothpanel-daemon"

