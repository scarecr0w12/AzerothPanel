# Changelog

All notable changes to AzerothPanel are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] – 2026-03-01

### Added – Playerbots Database Support

The database manager now auto-detects when the `mod-playerbots` module is
installed and exposes the `acore_playerbots` database alongside the standard
three AzerothCore databases.

#### `backend/app/services/panel_settings.py`
- Added `AC_PLAYERBOTS_DB_*` defaults (`host`, `port`, `user`, `password`,
  `name`). All default to the same `acore` user / `acore_playerbots` database
  name used by the installer. Values are configurable from the Settings page.

#### `backend/app/core/database.py`
- Added `get_playerbots_db` async session factory, following the same dynamic
  credentials pattern as the other three database providers.

#### `backend/app/api/v1/endpoints/database.py`
- Added `_is_playerbots_available()` — checks whether
  `{AC_PATH}/modules/mod-playerbots` exists on disk to determine if the
  playerbots module is installed.
- Added `GET /database/available` endpoint that returns the list of queryable
  database targets. Always includes `auth`, `characters`, `world`; appends
  `playerbots` when the module directory is detected.
- All query, browse, table-list, and backup endpoints now accept `playerbots`
  as a valid target, guarded with a 404 when the module is absent.
- Backup (`POST /database/backup?database=playerbots` and `...=all`) uses the
  dedicated `AC_PLAYERBOTS_DB_*` credentials for the playerbots dump.

#### `frontend/src/types/index.ts`
- `DatabaseTarget` union type extended to include `'playerbots'`.

#### `frontend/src/services/api.ts`
- Added `dbApi.available()` — calls `GET /database/available` to retrieve the
  runtime list of usable database targets.

#### `frontend/src/pages/DatabaseManager.tsx`
- On load, fetches `/database/available` and shows the **Playerbots** database
  tab (purple) only when the backend reports it as available. The standard three
  tabs are always shown while the request is in-flight.

### Added – Persistent Server Management via Host Daemon

AzerothCore game servers previously ran as subprocesses of the backend Docker
container. Docker kills the entire container cgroup on restart, meaning
`worldserver` and `authserver` were terminated whenever the panel was updated or
restarted — even with `start_new_session=True`. This release fixes that.

#### `backend/ac_host_daemon.py` (new)
- Standalone asyncio **TCP** daemon listening on `127.0.0.1:7879` that runs **on
  the host machine** outside any Docker cgroup.
- Owns and manages `worldserver` / `authserver` processes so they survive panel
  container restarts.
- Persists process metadata (PID, binary path, start time) to a JSON state file
  (`/var/run/azerothpanel/ac-daemon-state.json`) so the daemon can re-attach to
  already-running processes after its own restart.
- JSON-over-TCP protocol: single request → single response per connection.
  Supported commands: `ping`, `start`, `stop`, `status`, `list`, `console`.
- Stdin pipe kept open for every managed process so in-game console commands
  (`console` cmd) continue to work.
- TCP transport chosen deliberately: the backend uses `network_mode: host`, so
  `127.0.0.1` inside the container is the host loopback — no bind-mount needed.
  (A Unix-socket approach was abandoned because `/var/run` is a `tmpfs` on
  systemd hosts; the container mounts its own `tmpfs` at `/run`, which shadows
  the host bind-mount and hides the socket inside the container even though
  `docker inspect` shows the mount as configured.)

#### `backend/azerothpanel-daemon.service` (new)
- Systemd unit file for the host daemon.
- `KillMode=process` + `SendSIGKILL=no` — stopping the unit does **not** kill the
  game server child processes; they continue running independently.
- `Restart=on-failure` with 5 s delay for automatic daemon recovery.
- `RuntimeDirectory=azerothpanel` — systemd creates `/run/azerothpanel`
  before start (used for PID / state files).
- Uses `__PANEL_DIR__` placeholder; `make daemon-install` substitutes the real
  project path at install time — no hardcoded paths in the repo.

#### `backend/app/services/azerothcore/server_manager.py` (rewrite)
- Added `_daemon_send()` / `_daemon_available()` — async TCP client for the host
  daemon (`asyncio.open_connection`).
- All `_launch()` / `_stop()` calls now route through the daemon when available;
  fall back transparently to the previous direct-subprocess path when the daemon
  is unreachable (local dev, no daemon running).
- Added `get_process_status_async()` — queries the daemon for accurate CPU/memory
  stats; falls back to `psutil` if daemon absent.
- `send_console_command()` routes through daemon console command; falls back to
  in-process stdin pipe.
- Fallback warnings logged clearly so operators know to run `make daemon-start`.

#### `backend/app/api/v1/endpoints/server.py`
- `GET /api/v1/server/status` now calls `get_process_status_async()` so it
  queries the daemon rather than doing a blocking psutil scan.

#### `docker-compose.yml`
- Backend service: replaced `AC_DAEMON_SOCKET` with `AC_DAEMON_HOST` and
  `AC_DAEMON_PORT` environment variables (`127.0.0.1` / `7879` by default).
- Removed the Unix-socket bind-mount (`/var/run/azerothpanel`) — no longer
  needed with TCP transport.

#### `.env.example`
- Replaced `AC_DAEMON_DIR` / `AC_DAEMON_SOCKET` with `AC_DAEMON_HOST` and
  `AC_DAEMON_PORT` variables; updated comments to explain the TCP design.

#### `Makefile`
- Added `daemon-start` — launches daemon in background via `nohup`, writes PID
  file, guards against double-start.
- Added `daemon-stop` — sends SIGTERM to daemon PID and removes PID file.
- Added `daemon-restart` — stop then start.
- Added `daemon-status` — shows running/stopped state and queries daemon `list`
  command via inline Python TCP socket client.
- Added `daemon-install` — substitutes `$(PWD)` into `__PANEL_DIR__` placeholder
  in the service file, copies to `/etc/systemd/system/`, runs `systemctl enable`
  + `systemctl start`. Fixes previous hardcoded-path issue.
- `PYTHON` variable auto-selects the backend venv's Python (which has `psutil`
  installed) before falling back to system `python3`.

### Fixed

#### `backend/azerothpanel-daemon.service` — `status=203/EXEC` crash loop
- The service file previously hardcoded `WorkingDirectory=/opt/azerothpanel` and
  `ExecStart=/opt/azerothpanel/...`. If AzerothPanel is installed in any other
  location (e.g. `/root/azerothpanel`) systemd reported `status=203/EXEC` and
  the daemon crash-looped on every boot without managing any processes.
- Fixed by replacing all hardcoded paths with the `__PANEL_DIR__` placeholder;
  `make daemon-install` now runs `sed -i "s|__PANEL_DIR__|$(PWD)|g"` before
  copying to `/etc/systemd/system/`.

#### Unix-socket visibility inside Docker container
- Even with the bind-mount configured, the Unix socket was invisible inside the
  container (`ls /var/run/azerothpanel/` showed an empty directory).
- Root cause: `/var/run` → `/run` (symlink) on modern systemd systems; `/run` is
  a `tmpfs`. Docker mounts a fresh `tmpfs` at the container's `/run`, which
  shadows the host bind-mount entirely — the socket existed on the host but was
  hidden by the container's overlaid `tmpfs`.
- Fixed by switching IPC from Unix socket to **TCP on `127.0.0.1:7879`**. Because
  the backend uses `network_mode: host`, the container shares the host's network
  namespace, so `127.0.0.1` inside the container is the same as the host loopback
  — no bind-mount or volume required.

#### `backend/azerothpanel-daemon.service` — servers stop on daemon/container restart
- `RuntimeDirectory=azerothpanel` caused systemd to **delete**
  `/run/azerothpanel/` (including `ac-daemon-state.json`) every time the service
  stopped. On the next start, `_load_state()` found no state file and could not
  re-attach to the running `worldserver`/`authserver` processes — effectively
  losing track of them and treating them as stopped.
- Fixed by adding `RuntimeDirectoryPreserve=yes`. The state file now survives
  daemon restarts (and Docker container restarts), allowing the daemon to
  re-attach to still-running game servers on startup.

- Screenshots for all panel pages added to `docs/screenshots/`.
- Full documentation pass: README, all `docs/` pages updated and proofread.

---

## [1.2.0] – 2025 (1149074)

### Added

#### Module Manager (`/api/v1/modules` + `src/pages/ModuleManager.tsx`)
- Browse the AzerothCore community module catalogue (fetched from GitHub).
- One-click install: clones module repository into the AC modules directory.
- List and remove installed modules.

#### Config Editor (`/api/v1/configs` + `src/pages/ConfigEditor.tsx`)
- In-browser syntax-highlighted Monaco editor for `.conf` files.
- Lists all editable config files (`worldserver.conf`, `authserver.conf`, and
  any module configs present in the installation).
- Save changes directly to disk with in-panel feedback.

#### Server Control improvements
- SOAP-based GM command execution (`POST /api/v1/server/command`).
- Global in-game announcement endpoint (`POST /api/v1/server/announce`).
- Host system information endpoint (`GET /api/v1/server/info`).

---

## [1.1.0] – 2025 (2da8660)

### Added

#### Data Extraction (`/api/v1/data-extraction` + `src/pages/DataExtraction.tsx`)
- **Download mode**: fetch pre-extracted client data from AzerothCore GitHub
  releases (~1.5 GB). Recommended for new installations.
- **Extract mode**: run the `mapextractor`, `vmap4extractor`, `vmap4assembler`,
  and `mmaps_generator` tools against a local WoW 3.3.5a client.
- Server-Sent Events (SSE) progress streaming for both modes.
- Cancel endpoint (`POST /cancel`) to abort a running extraction.
- `GET /status` returns current progress and which data types are present
  (`has_dbc`, `has_maps`, `has_vmaps`, `has_mmaps`).
- `CLIENT_PATH` bind-mount in `docker-compose.yml` for local client access.

### Fixed
- Various UI layout regressions on smaller viewports.
- WebSocket reconnect logic improved — exponential back-off with cap.
- Log viewer: prevent duplicate entries when WebSocket reconnects.

---

## [1.0.0] – 2025 (f6ec622 / 93812fd)

Initial public release.

### Added

#### Infrastructure
- `docker-compose.yml` with `backend` (FastAPI, `network_mode: host`) and
  `frontend` (nginx with reverse proxy) services.
- `nginx.conf` proxying `/api/` and `/ws/` to backend on port 8000.
- `backend/Dockerfile`: Python 3.12-slim, Oracle MySQL 8.x dev headers (required
  for AzerothCore's `mysql_ssl_mode`/`SSL_MODE_DISABLED`), full C/C++ build
  toolchain pre-installed.
- `frontend/Dockerfile`: multi-stage build (Node 20 → Vite build → nginx).
- Named Docker volumes: `panel_data` (SQLite DB), `pip_cache`.
- MySQL UNIX socket bind-mount (`/var/run/mysqld`) for `auth_socket` installs.
- `Makefile` developer shortcuts: `install`, `dev`, `backend`, `frontend`,
  `lint`, `docker-build`, `docker-quick`, `docker-up`, `docker-down`,
  `docker-logs`, `docker-restart`.
- `.env.example` + `backend/.env.example` with all configurable variables.

#### Backend — FastAPI application (`backend/app/`)
- `main.py`: app factory, CORS middleware (allow-all with credentials mode using
  `allow_origin_regex`), lifespan event for DB init and settings seed.
- `core/config.py`: Pydantic `BaseSettings` for all env vars.
- `core/database.py`: async SQLAlchemy engine + session factory targeting
  `panel.db` SQLite.
- `core/security.py`: HS256 JWT create/verify, `get_current_user` dependency,
  bcrypt password hashing.
- `models/panel_models.py`: `PanelSettings` ORM model.
- `models/schemas.py`: Pydantic schemas for all request/response bodies.
- `services/panel_settings.py`: CRUD helpers with async SQLAlchemy; `seed_defaults()`
  called at startup.

#### Backend — API endpoints (`/api/v1/`)
- **Auth** (`/auth`): form-body login, JSON login, `/me`. JWT Bearer tokens.
- **Server Control** (`/server`): start/stop/restart `worldserver`/`authserver`
  via psutil + subprocess; status with PID/CPU/memory; SOAP command proxy; host
  info; per-process console command support.
- **Player Management** (`/players`): online player list (SOAP), account list
  (search, pagination), character list and detail, ban/unban, kick, announce,
  stat modification.
- **Logs** (`/logs`): list sources, tail N lines, file size, download log file.
- **Database Manager** (`/database`): list tables, SQL query execution (read-only
  enforcement), table browser with pagination, `mysqldump` backup.
- **Installation** (`/installation`): run AzerothCore data installation steps
  (SSE stream), read/write `worldserver.conf` and `authserver.conf` as key-value
  stores.
- **Compilation** (`/compilation`): trigger CMake build with SSE streaming output,
  build status.
- **Settings** (`/settings`): get/put all panel settings, MySQL connection test.
- **WebSocket log streaming** (`/ws/logs/{source}`): real-time log tailing via
  asyncio file watching.

#### Services
- `services/azerothcore/server_manager.py`: psutil-based process discovery,
  asyncio subprocess launch with `start_new_session=True`, SIGTERM/SIGKILL stop
  with timeout, stdin pipe for in-game commands, binary/config/data validation
  before launch.
- `services/azerothcore/compiler.py`: CMake build runner, async generator
  yielding output lines for SSE.
- `services/azerothcore/installer.py`: step-based AC data installation runner.
- `services/azerothcore/module_manager.py`: git clone/remove for modules.
- `services/azerothcore/soap_client.py`: httpx-based SOAP/XML-RPC client for
  in-game GM commands.
- `services/azerothcore/data_extractor.py`: download and client extraction
  orchestration.
- `services/logs/log_manager.py`: async log file reading and tailing.

#### Frontend — React + TypeScript (`frontend/src/`)
- Vite + TypeScript strict mode, Tailwind CSS, React Router v6.
- **Pages**: `Login`, `Dashboard`, `ServerControl`, `PlayerManagement`,
  `LogViewer`, `DatabaseManager`, `Compilation`, `Installation`, `DataExtraction`,
  `ModuleManager`, `ConfigEditor`, `Settings`.
- **Components**: `Layout`, `Header`, `Sidebar` (collapsible, icon+label nav);
  `Button`, `Card`, `StatusBadge`, `Toast`.
- **Hooks**: `useWebSocket` (generic, exponential reconnect), `useServerStatus`
  (polls `/api/v1/server/status` on interval).
- **Store**: Zustand with auth token + server status slices.
- `services/api.ts`: Axios instance with Bearer token injector and typed helpers
  for every endpoint.
- `types/index.ts`: shared TypeScript interfaces mirroring backend Pydantic
  schemas.

#### Documentation
- `README.md`: features table, architecture diagram, quick start, make targets,
  project structure, security notes.
- `docs/installation.md`: Docker quick start, manual install, reverse proxy,
  update/uninstall.
- `docs/configuration.md`: full environment variable reference, in-panel settings
  reference, security checklist.
- `docs/development.md`: local setup, backend/frontend conventions, adding
  endpoints/pages, UI reference.
- `docs/api.md`: full endpoint reference with request/response examples.
- `LICENSE`: MIT.
