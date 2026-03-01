# Development Guide

This document covers setting up a local development environment, the project conventions, and how to contribute.

---

## Table of Contents

1. [Local setup (no Docker)](#local-setup-no-docker)
2. [Backend development](#backend-development)
3. [Frontend development](#frontend-development)
4. [Code style & conventions](#code-style--conventions)
5. [Adding a new API endpoint](#adding-a-new-api-endpoint)
6. [Adding a new frontend page](#adding-a-new-frontend-page)
7. [Environment variables in development](#environment-variables-in-development)
8. [Host daemon in development](#host-daemon-in-development)
9. [UI Reference](#ui-reference)
10. [Troubleshooting](#troubleshooting)

---

## Local setup (no Docker)

### Requirements

- Python 3.11+
- Node.js 20 LTS + npm
- A running AzerothCore MySQL instance accessible from your machine
- (Optional) A running worldserver on the same machine for SOAP commands

### Quick start

```bash
git clone https://github.com/scarecr0w12/AzerothPanel.git
cd AzerothPanel

# Install deps
make install          # runs install-backend + install-frontend

# Copy environment templates
cp backend/.env.example backend/.env
# Set SECRET_KEY, PANEL_ADMIN_USER, PANEL_ADMIN_PASSWORD in backend/.env

# Start both processes in parallel (requires make 4.x)
make dev
```

- Backend: [http://localhost:8000](http://localhost:8000)
- Frontend: [http://localhost:5173](http://localhost:5173) (with HMR)
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Backend development

### Virtual environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running with auto-reload

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Project layout

```
backend/app/
├── main.py             # App factory: registers routers, CORS, lifespan event
├── core/
│   ├── config.py       # Pydantic BaseSettings — all env vars typed here
│   ├── database.py     # Async SQLAlchemy engine + session factory
│   └── security.py     # JWT create/verify, password hashing, `get_current_user`
├── models/
│   ├── panel_models.py # SQLAlchemy ORM models (PanelSettings, etc.)
│   └── schemas.py      # Pydantic schemas for request/response bodies
├── api/v1/
│   ├── router.py       # Aggregates all endpoint routers under /api/v1
│   └── endpoints/      # One file per feature domain
├── api/websockets/
│   └── logs.py         # WebSocket handler for live log tailing
└── services/
    ├── panel_settings.py           # CRUD helpers for panel settings
    └── azerothcore/
        ├── server_manager.py       # Daemon-aware process control; falls back to direct subprocess
        ├── compiler.py             # Runs cmake/make, yields output lines
        ├── installer.py            # Runs AC installation steps
        └── soap_client.py          # HTTP SOAP client (httpx)
```

### Adding a Python dependency

1. Activate the venv: `source backend/.venv/bin/activate`
2. Install: `pip install <package>`
3. Freeze: `pip freeze > backend/requirements.txt`

---

## Frontend development

### Running the dev server

```bash
cd frontend
npm install
npm run dev
```

The Vite config proxies `/api/` and `/ws/` to `http://localhost:8000`, so you can develop with the real backend without CORS issues.

### Build for production

```bash
cd frontend
npm run build    # outputs to frontend/dist/
```

### Project layout

```
frontend/src/
├── App.tsx              # React Router routes
├── main.tsx             # Entry point, Zustand store hydration
├── index.css            # Tailwind base
├── pages/               # Full-page views (one per route)
├── components/
│   ├── layout/          # Header, Sidebar, Layout wrapper
│   └── ui/              # Reusable primitives (Button, Card, StatusBadge)
├── hooks/
│   ├── useWebSocket.ts  # Generic WebSocket hook with reconnect
│   └── useServerStatus.ts  # Polls /api/v1/server/status
├── services/api.ts      # Axios instance + all typed API calls
├── store/index.ts       # Zustand global store (auth token, server state)
└── types/index.ts       # Shared TypeScript interfaces
```

### Type-checking

```bash
make lint
# or
cd frontend && npx tsc --noEmit
```

---

## Code style & conventions

### Backend

- Follow PEP 8; use 4-space indentation.
- Async all the way: use `async def` for all route handlers and service functions.
- All request/response bodies are typed with **Pydantic schemas** in `models/schemas.py`.
- Raise `HTTPException` with appropriate status codes; do not return raw error strings.
- Business logic belongs in `services/`, not in endpoint handlers.
- Use dependency injection (`Depends`) for auth, database sessions, and settings.

### Frontend

- TypeScript strict mode is enabled — no `any` types without a clear justification.
- Functional components with hooks only; no class components.
- API calls live in `services/api.ts`; pages do not call `axios` directly.
- Shared types go in `types/index.ts`.
- Use Tailwind utility classes; avoid custom CSS unless unavoidable.

---

## Adding a new API endpoint

1. **Create or update the endpoint file** in `backend/app/api/v1/endpoints/`.

   ```python
   # backend/app/api/v1/endpoints/example.py
   from fastapi import APIRouter, Depends
   from app.core.security import get_current_user

   router = APIRouter(prefix="/example", tags=["Example"])

   @router.get("/hello")
   async def hello(_: dict = Depends(get_current_user)):
       return {"message": "Hello from the new endpoint"}
   ```

2. **Register it in the router** (`backend/app/api/v1/router.py`):

   ```python
   from app.api.v1.endpoints import example
   api_router.include_router(example.router)
   ```

3. **Add request/response schemas** to `backend/app/models/schemas.py` if needed.

4. **Expose it in the frontend** by adding a typed function to `frontend/src/services/api.ts`:

   ```typescript
   export const getHello = () =>
     api.get<{ message: string }>("/example/hello").then(r => r.data);
   ```

---

## Adding a new frontend page

1. **Create the page component** in `frontend/src/pages/MyPage.tsx`.

2. **Add the route** in `frontend/src/App.tsx`:

   ```tsx
   import MyPage from "./pages/MyPage";
   // inside <Routes>:
   <Route path="/my-page" element={<MyPage />} />
   ```

3. **Add a sidebar link** in `frontend/src/components/layout/Sidebar.tsx`:

   ```tsx
   { path: "/my-page", label: "My Page", icon: <SomeIcon /> }
   ```

---

## Environment variables in development

The backend reads `backend/.env` via `pydantic-settings`. Any variable in `backend/.env.example` can be overridden.

The frontend does not use `.env` files at runtime — Vite `import.meta.env` variables are baked in at build time. The only variable used is the implicit `VITE_API_BASE` (defaulting to the same origin), which is handled via the Vite proxy in development.

---

## Host daemon in development

The host daemon (`backend/ac_host_daemon.py`) is optional in a local dev setup.
If the TCP port (`AC_DAEMON_PORT`, default `7879`) is unreachable,
`server_manager.py` automatically falls back to spawning processes directly.
This means **no daemon is required** to develop or test the panel locally.

To test daemon-mode behaviour locally:

```bash
# Start the daemon in a separate terminal (uses the backend venv's Python)
make daemon-start

# Confirm it is reachable
make daemon-status

# Run the backend — it will detect the daemon and route via it
make backend
```

The daemon protocol is **JSON-over-TCP** (one request / one response per
connection, newline-terminated). You can probe it manually:

```bash
python3 -c "
import socket, json
s = socket.create_connection(('127.0.0.1', 7879))
s.sendall(json.dumps({'cmd': 'list'}).encode() + b'\n')
print(json.dumps(json.loads(s.recv(65536)), indent=2))
s.close()
"
```

### Daemon commands reference

| Command | Optional fields | Description |
|---|---|---|
| `ping` | — | Health check; returns `{"success": true, "message": "pong"}`. |
| `start` | `name`, `binary`, `cwd` | Launch a server process. |
| `stop` | `name` | Gracefully stop (`SIGTERM → SIGKILL`). |
| `status` | `name` | Return running state, PID, CPU, memory. |
| `list` | — | Status of all tracked services. |
| `console` | `name`, `command` | Write a command to the server's stdin. |
| `version` | `project_dir` | Return current git commit, branch, tag, and commits behind origin. |
| `update` | `project_dir` | `git pull --rebase` then `docker compose up --build -d`; returns combined output. |

---

## UI Reference

The following screenshots show the current state of each panel page. Useful as reference when developing new features or debugging layout regressions.

### Login

![Login](screenshots/login.png)

### Dashboard

![Dashboard](screenshots/dashboard.png)

### Server Control

![Server Control](screenshots/server_control.png)

### Log Viewer

![Log Viewer](screenshots/log_viewer.png)

### Player Management

![Players](screenshots/players.png)

### Database Manager

![Database](screenshots/database.png)

### Compilation

![Compilation](screenshots/compilation.png)

### Installation & Setup

![Installation](screenshots/installation.png)

### Data Extraction

![Data Extraction](screenshots/data_extraction.png)

### Module Manager

![Modules](screenshots/modules.png)

### Config Editor

![Config Editor](screenshots/config_editor.png)

### Settings

![Settings](screenshots/settings.png)

---

## Troubleshooting

Check what is using port 8000:

```bash
sudo lsof -i :8000
```

### Frontend shows "Network Error" on API calls

Ensure the backend is running on port 8000 and `vite.config.ts` proxy target matches:

```typescript
proxy: {
  "/api": "http://localhost:8000",
  "/ws":  "http://localhost:8000",
}
```

### SOAP commands return "Connection refused"

- Confirm `SOAP.Enabled = 1` in `worldserver.conf`.
- Confirm the worldserver is running.
- Verify the SOAP host/port/credentials in the panel's **Settings** page.

### Panel shows "Unauthorized" after a restart

JWT tokens are signed with `SECRET_KEY`. If you changed `SECRET_KEY`, existing tokens are invalidated. Log in again.

### Docker: backend cannot reach MySQL

The backend container uses `network_mode: host`, meaning `127.0.0.1` inside the container resolves to the host. If MySQL is bound only to a specific interface, ensure it is accessible from the host's loopback or update the MySQL host in **Settings** to the correct IP.

### worldserver / authserver stops when I restart the panel containers

This happens when the game servers are running as subprocesses of the backend
container. Docker kills the entire container cgroup on restart.

**Fix:** start the host daemon so it owns the server processes outside Docker:

```bash
# One-time background start
make daemon-start

# Or install as a persistent systemd service
sudo make daemon-install
```

Once the daemon is running, any server started through the panel will be a child
of the daemon (host cgroup), not the Docker container. Container restarts will
not affect running game servers.

### Daemon is running but panel still shows servers as stopped

- Verify `AC_DAEMON_HOST` / `AC_DAEMON_PORT` in `docker-compose.yml` / `backend/.env` match the values used to start the daemon.
- The backend uses `network_mode: host`, so `127.0.0.1` inside the container is the host loopback — no bind-mount is needed.
- Run `make daemon-status` on the host to confirm the daemon is listening.
