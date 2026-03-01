# AzerothPanel

A modern, web-based management panel for [AzerothCore](https://www.azerothcore.org/) WoW private servers.

AzerothPanel wraps everything a server administrator needs — start/stop servers, manage players, run GM commands, tail logs in real time, query databases, trigger builds, and configure the entire AzerothCore installation — into a clean React UI backed by a FastAPI REST + WebSocket API.

---

## Features

| Category | Capabilities |
|---|---|
| **Server Control** | Start, stop & restart worldserver / authserver; **multi-instance worldserver management** with independent per-process start/stop/restart/console; SOAP GM command execution; in-game server announcements |
| **Multi-Instance Provisioning** | 2-step wizard creates additional worldserver instances from the UI; auto-generates a patched `worldserver.conf` with custom ports, realm name and realm ID; per-instance config tab for live editing |
| **Player Management** | List online players, browse accounts & characters, ban/unban accounts, kick players, bulk announcements, character stat modification |
| **Log Viewer** | Real-time log streaming (WebSocket), paginated log history, log download, multiple log sources |
| **Database Manager** | Browse world/auth/characters/playerbots databases, execute SQL queries (read-only safety checks), table browser, database backup; **playerbots tab auto-detected** when `mod-playerbots` is installed |
| **Compiler** | Trigger AzerothCore CMake builds with streaming SSE progress output; **Pull Latest Source** (`git pull`) from the same page |
| **Installer** | Run the AzerothCore data installation steps with live progress, read/edit `worldserver.conf` and `authserver.conf` in-browser |
| **Data Extraction** | Download pre-extracted client data from AzerothCore releases, or extract from local WoW 3.3.5a client (DBC, Maps, VMaps, MMaps) |
| **Module Manager** | Browse, install, and remove AzerothCore modules from the community catalogue; **per-module and bulk `git pull` updates** |
| **Config Editor** | In-browser syntax-highlighted editor for `worldserver.conf`, `authserver.conf`, and installed module configs |
| **Panel Self-Update** | Check version and update the panel (git pull + Docker rebuild) from the Settings page or via `make update` — no shell access required |
| **Settings** | Configure all AzerothCore paths, MySQL credentials, SOAP endpoint, and connection test — entirely UI-driven; no `.env` edits required after initial setup |
| **Authentication** | JWT bearer tokens, single admin user, configurable session length |

---

## Screenshots

<table>
<tr>
  <td align="center"><strong>Login</strong><br><img src="docs/screenshots/login.png" width="420"></td>
  <td align="center"><strong>Dashboard</strong><br><img src="docs/screenshots/dashboard.png" width="420"></td>
</tr>
<tr>
  <td align="center"><strong>Server Control</strong><br><img src="docs/screenshots/server_control.png" width="420"></td>
  <td align="center"><strong>Player Management</strong><br><img src="docs/screenshots/players.png" width="420"></td>
</tr>
<tr>
  <td align="center"><strong>Log Viewer</strong><br><img src="docs/screenshots/log_viewer.png" width="420"></td>
  <td align="center"><strong>Database Manager</strong><br><img src="docs/screenshots/database.png" width="420"></td>
</tr>
<tr>
  <td align="center"><strong>Module Manager</strong><br><img src="docs/screenshots/modules.png" width="420"></td>
  <td align="center"><strong>Config Editor</strong><br><img src="docs/screenshots/config_editor.png" width="420"></td>
</tr>
<tr>
  <td align="center"><strong>Compilation</strong><br><img src="docs/screenshots/compilation.png" width="420"></td>
  <td align="center"><strong>Installation & Setup</strong><br><img src="docs/screenshots/installation.png" width="420"></td>
</tr>
<tr>
  <td align="center"><strong>Data Extraction</strong><br><img src="docs/screenshots/data_extraction.png" width="420"></td>
  <td align="center"><strong>Settings</strong><br><img src="docs/screenshots/settings.png" width="420"></td>
</tr>
</table>

---

## Architecture

```
┌─────────────────────────────────────┐
│           Browser (React)           │
│  Vite · TypeScript · Tailwind CSS   │
│  Zustand state · React Router       │
└──────────────┬──────────────────────┘
               │  HTTP /api/    WebSocket /ws/
               ▼
┌─────────────────────────────────────┐
│          nginx (port 80)            │
│  static files + reverse proxy       │
└──────────────┬──────────────────────┘
               │  host.docker.internal:8000
               ▼
┌─────────────────────────────────────┐
│   FastAPI backend (port 8000)       │
│  REST API v1 · WebSocket logs       │
│  SQLite (panel.db) · JWT auth       │
└──────────────┬──────────────────────┘
               │  Unix socket  /var/run/azerothpanel/ac-panel.sock
               ▼
┌─────────────────────────────────────┐
│   ac_host_daemon.py  (HOST)         │  ← runs outside Docker
│  owns worldserver / authserver PIDs │
│  survives container restarts        │
└──────────────┬──────────────────────┘
               │  subprocess  +  MySQL / SOAP
               ▼
┌─────────────────────────────────────┐
│     AzerothCore (host machine)      │
│  worldserver · authserver · MySQL   │
└─────────────────────────────────────┘
```

The backend container uses `network_mode: host` so it can reach MySQL and the SOAP interface on `127.0.0.1`. The frontend container reaches the backend via `host.docker.internal`.

The **host daemon** (`ac_host_daemon.py`) is the key to persistence: it runs directly on the host (not inside any Docker container) and owns the AzerothCore server processes. Because it lives in the host's cgroup rather than the panel container's cgroup, the game servers keep running when Docker restarts the panel. The backend and daemon communicate via a bind-mounted Unix socket.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- AzerothCore installed on the host (default path `/opt/azerothcore`)
- MySQL/MariaDB with the AzerothCore databases accessible from the host

### 1 — Clone the repository

```bash
git clone https://github.com/scarecr0w12/AzerothPanel.git
cd AzerothPanel
```

### 2 — Configure environment

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Edit `backend/.env` at minimum:

```dotenv
SECRET_KEY=<output of: openssl rand -hex 32>
PANEL_ADMIN_USER=admin
PANEL_ADMIN_PASSWORD=change_me
```

Edit `.env` if AzerothCore is not at `/opt/azerothcore` or you want a different port:

```dotenv
AC_PATH=/opt/azerothcore
PANEL_PORT=80
```

### 3 — Start the host daemon (once, before Docker)

The daemon must run on the host so AzerothCore servers survive Docker restarts:

```bash
# Option A: background process (until next reboot)
make daemon-start

# Option B: install as a systemd service (auto-starts on every boot — recommended)
sudo make daemon-install
```

Verify it is running:

```bash
make daemon-status
```

### 4 — Start the panel

```bash
make docker-up
# or
docker compose up --build -d
```

Open [http://localhost](http://localhost) (or the port you set in `PANEL_PORT`).

### 5 — Initial setup

Log in with the admin credentials from `backend/.env`, then navigate to **Settings** to configure:

![Login screen](docs/screenshots/login.png)

- AzerothCore installation path
- MySQL host/port/user/password for each database (world, auth, characters)
- SOAP host/port/user/password for in-game command execution

![Settings page](docs/screenshots/settings.png)

Use **Test Connection** to verify each database before saving.

---

## Configuration

See [docs/configuration.md](docs/configuration.md) for a full reference of all environment variables and in-panel settings.

---

## Development

See [docs/development.md](docs/development.md) for local dev setup without Docker.

---

## API Reference

The backend exposes a versioned REST API at `/api/v1` and a WebSocket endpoint at `/ws/logs`. Interactive Swagger docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) when running.

See [docs/api.md](docs/api.md) for a complete endpoint reference.

---

## Make Targets

```
make install           Install all dependencies (backend + frontend)
make dev               Run backend + frontend in development mode (no Docker)
make backend           Run only the FastAPI backend on :8000
make frontend          Run only the Vite dev server on :5173
make lint              TypeScript type-check

make docker-build      Build Docker images (no cache)
make docker-quick      Build Docker images (with cache)
make docker-up         Build & start containers in background
make docker-down       Stop and remove containers
make docker-logs       Tail logs from all containers
make docker-restart    Rebuild & restart all containers

# Panel updates
make version           Print current git tag, branch, commit, and upstream lag
make update            git pull --rebase then rebuild & restart containers

# Host Process Daemon — run on the HOST machine to keep AC servers alive
make daemon-start      Launch daemon in background (until reboot)
make daemon-stop       Stop the daemon
make daemon-restart    Restart the daemon
make daemon-status     Show daemon state + managed process list
make daemon-install    Install daemon as a systemd service (auto-start on boot)
```

---

## Project Structure

```
AzerothPanel/
├── docker-compose.yml         # Production deployment
├── nginx.conf                 # Reverse proxy / static file config
├── Makefile                   # Developer shortcuts
├── .env.example               # Docker Compose variables
│
├── backend/                   # FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── ac_host_daemon.py          # HOST daemon – owns worldserver/authserver
│   ├── azerothpanel-daemon.service # systemd unit for the host daemon
│   └── app/
│       ├── main.py            # Application factory, CORS, lifespan
│       ├── api/v1/
│       │   ├── router.py      # Route aggregation
│       │   └── endpoints/     # auth, server, instances, players, logs,
│       │                      # database, installation, compilation,
│       │                      # modules, configs, settings
│       ├── api/websockets/
│       │   └── logs.py        # Real-time log streaming
│       ├── core/
│       │   ├── config.py      # Pydantic Settings
│       │   ├── database.py    # SQLAlchemy async engine (panel DB)
│       │   └── security.py    # JWT helpers
│       ├── models/
│       │   ├── panel_models.py # SQLAlchemy ORM models
│       │   └── schemas.py     # Pydantic request/response schemas
│       └── services/
│           ├── panel_settings.py         # Settings CRUD
│           └── azerothcore/
│               ├── server_manager.py     # Process control (daemon or direct)
│               ├── instance_seeder.py    # Seeds default worldserver instance
│               ├── compiler.py           # CMake build runner
│               ├── installer.py          # Data installation steps
│               ├── module_manager.py     # Module clone/remove/git-pull
│               └── soap_client.py        # SOAP RPC client
│
└── frontend/                  # React + TypeScript
    ├── Dockerfile             # Multi-stage build → nginx
    ├── vite.config.ts
    └── src/
        ├── pages/             # Dashboard, ServerControl, Players, Logs,
        │                      # DatabaseManager, Compilation, Installation,
        │                      # ModuleManager, ConfigEditor, Settings, Login
        ├── components/        # Layout (Header/Sidebar) + UI primitives
        ├── services/api.ts    # Axios instance + typed API helpers
        ├── store/index.ts     # Zustand global store
        ├── hooks/             # useWebSocket, useServerStatus, useInstances
        └── types/index.ts     # Shared TypeScript interfaces
```

---

## Security Notes

- **Change the default credentials** (`PANEL_ADMIN_USER` / `PANEL_ADMIN_PASSWORD`) before exposing the panel to any network.
- **Generate a strong `SECRET_KEY`**: `openssl rand -hex 32`
- The panel is designed for **trusted private network use**. Do not expose port 80 to the public internet without additional protection (firewall, VPN, reverse-proxy with TLS).
- SQL queries executed through the Database Manager are subject to a server-side read-only safety check (blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`).

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of changes.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

- [AzerothCore](https://www.azerothcore.org/) — the open-source WoW emulator this panel is built for
- [FastAPI](https://fastapi.tiangolo.com/) — backend framework
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) — frontend toolchain
- [Tailwind CSS](https://tailwindcss.com/) — utility-first styling
