# Changelog

All notable changes to AzerothPanel are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] – 2026-03-04

### Summary

| Area | Change |
|---|---|
| **Backup & Restore** | Full backup and restore system supporting Local filesystem, SFTP/FTP, AWS S3, Google Drive, and OneDrive as destinations; backs up AzerothCore config files, all three game databases, and server binary/data files; secondary worldserver instance config files (arbitrary paths) are correctly included |

---

### Added – Backup & Restore System

A complete backup and restore subsystem has been added to AzerothPanel, covering all critical server assets and supporting five remote storage providers.

#### Backend — data model

##### `backend/app/models/panel_models.py`
- New `BackupDestination` ORM model: `id`, `name`, `type` (`local` / `sftp` / `ftp` / `s3` / `gdrive` / `onedrive`), `config` (JSON blob), `enabled` (Boolean), `created_at`.
- New `BackupJob` ORM model: `id`, `destination_id`, `status` (`pending` / `running` / `completed` / `failed`), `include_configs`, `include_databases`, `include_server_files`, `filename`, `local_path`, `size_bytes`, `started_at`, `completed_at`, `error`, `notes`.
- `Boolean` added to SQLAlchemy imports.

##### `backend/app/core/database.py`
- `run_panel_db_migrations()` v1.3 block: `CREATE TABLE IF NOT EXISTS backup_destinations` and `CREATE TABLE IF NOT EXISTS backup_jobs` — safe on every startup.

##### `backend/app/models/schemas.py`
- New schemas: `BackupDestinationCreate`, `BackupDestinationUpdate`, `BackupDestinationSchema`, `BackupJobCreate`, `BackupJobSchema`, `RestoreRequest`.

#### Backend — service

##### `backend/app/services/backup/backup_manager.py`  *(new file, ~1 050 lines)*
Six storage-provider classes, each implementing `upload()`, `download()`, `delete()`, `list_files()`, and `test()`:

| Class | Provider | Key dependency |
|---|---|---|
| `LocalStorage` | Local filesystem | stdlib `pathlib` |
| `SftpStorage` | SFTP | `paramiko` |
| `FtpStorage` | FTP/FTPS | stdlib `ftplib` |
| `S3Storage` | AWS S3 / S3-compatible | `boto3` |
| `GoogleDriveStorage` | Google Drive | `google-api-python-client`, `google-auth` |
| `OneDriveStorage` | Microsoft OneDrive | `msal`, `httpx` |

Core functions:

- `run_backup_sync(job_id, dest_type, dest_config, include_configs, include_databases, include_server_files, settings, progress_callback, instance_conf_files=None)` — builds a `.tar.gz` archive containing:
  - `configs/` — global `AC_CONF_PATH/*.conf` files.
  - `configs/instances/{safe_name}/{filename}` — per-instance worldserver config files from arbitrary absolute paths (new in v1.3).
  - `databases/` — `mysqldump` of auth, world, and characters databases.
  - `server/` — AzerothCore binaries and data directory.
- `run_restore_sync(...)` — extracts a `.tar.gz` archive; global configs go to `AC_CONF_PATH`, per-instance configs are written back to their original absolute paths.
- `run_backup_stream(...)` / `run_restore_stream(...)` — async SSE wrappers using `asyncio.Queue` + `run_in_executor`; both accept `instance_conf_files`.
- `_get_storage(dest_type, config)` factory returns the appropriate provider instance.

##### `backend/requirements.txt`
- Added: `paramiko==3.5.0`, `boto3==1.35.86`, `google-auth==2.37.0`, `google-api-python-client==2.157.0`, `msal==1.31.1`.

#### Backend — API

##### `backend/app/api/v1/endpoints/backup.py`  *(new file, 19 endpoints)*

| Method | Path | Description |
|---|---|---|
| `GET` | `/backup/destinations` | List all backup destinations |
| `POST` | `/backup/destinations` | Create a new destination |
| `GET` | `/backup/destinations/{id}` | Get a single destination |
| `PUT` | `/backup/destinations/{id}` | Update a destination |
| `DELETE` | `/backup/destinations/{id}` | Delete a destination |
| `POST` | `/backup/destinations/{id}/test` | Test connectivity / credentials |
| `GET` | `/backup/destinations/{id}/files` | List archive files stored at a destination |
| `GET` | `/backup/jobs` | List all backup jobs |
| `GET` | `/backup/jobs/{id}` | Get a single job |
| `DELETE` | `/backup/jobs/{id}` | Delete a job record |
| `GET` | `/backup/jobs/{id}/files` | List files associated with a job |
| `DELETE` | `/backup/jobs/{id}/files/{filename}` | Delete a specific archive file |
| `POST` | `/backup/run` | Start a new backup (SSE stream) |
| `POST` | `/backup/restore` | Restore from a backup job (SSE stream) |

`POST /backup/run` creates a `BackupJob` record (status=running), queries all `WorldServerInstance` rows that have a non-empty `conf_path`, and passes the resulting `(display_name, conf_path)` pairs through `run_backup_stream` so every secondary worldserver's config is archived.

`POST /backup/restore` validates the job is `completed` before streaming; queries instance conf paths and passes them to `run_restore_stream` so each file is written back to its original absolute path.

##### `backend/app/api/v1/router.py`
- `backup` router imported and registered under `/api/v1`.

#### Frontend

##### `frontend/src/types/index.ts`
- New types: `BackupDestType` (union), `LocalConfig`, `SftpConfig`, `FtpConfig`, `S3Config`, `GDriveConfig`, `OneDriveConfig`, `BackupDestination`, `BackupJob`, `BackupFile`, `BackupDestinationCreate`, `BackupJobCreate`.

##### `frontend/src/services/api.ts`
- New `backupApi` object with methods: `listDestinations`, `createDestination`, `getDestination`, `updateDestination`, `deleteDestination`, `testDestination`, `listDestinationFiles`, `listJobs`, `getJob`, `deleteJob`, `listJobFiles`, `deleteJobFile`, `runBackup` (raw `fetch` for SSE), `restore` (raw `fetch` for SSE).

##### `frontend/src/pages/BackupManager.tsx`  *(new file, ~530 lines)*
Three-tab interface:

| Tab | Contents |
|---|---|
| **Destinations** | CRUD list with connection test; `DestinationModal` with type-selector and dynamic provider config fields |
| **Create Backup** | Destination picker, include checkboxes (Configs / Databases / Server Files), SSE log panel |
| **Job History** | Paginated job list with status badges; inline restore modal with options; expandable per-job file browser; delete job / delete file actions |

##### `frontend/src/App.tsx`
- `BackupManager` imported; `/backup` route added.

##### `frontend/src/components/layout/Sidebar.tsx`
- `Archive` icon from `lucide-react`; **Backup & Restore** nav item added to the Configure group.

---

## [Unreleased] – 2026-03-02

### Summary

| Area | Change |
|---|---|
| **Per-instance overrides** | Every worldserver instance can now define its own AC source path, build path, characters database credentials and SOAP credentials — seamless multi-realm support without touching global settings |
| **Structured application logging** | All backend modules now emit structured log lines to stdout **and** a rotating file at `<PANEL_LOG_DIR>/panel.log` (default `/data/logs/panel.log`) |
| **Instance-scoped operations** | Compilation, module management, database manager, log viewer and player management pages all show an instance selector when more than one instance exists; every API call passes `instance_id` or `ac_path` accordingly |
| **Named binary symlink** | When compiling for a specific instance (`process_name` supplied), the build step creates a `worldserver-<name>` symlink in the bin directory so the daemon can uniquely track each process |
| **Docker volume** | `panel_data` named volume replaced with a host-mounted `./data` directory so the SQLite DB and application logs are directly accessible on the host |
| **WebSocket URL fix** | `useWebSocket` now correctly appends `?token=…` vs `&token=…` based on whether the path already contains a query string |
| **HTTP request middleware** | New FastAPI middleware logs every request with method, path, status code and elapsed milliseconds |

---

### Added – Per-Instance Overrides (Multi-Realm Support)

Each `WorldServerInstance` can now carry its own credential/path overrides
that take precedence over the global panel Settings for all operations
that touch that instance.  Empty values silently fall back to the
global configuration, so single-realm setups require zero changes.

#### Backend — data model

##### `backend/app/models/panel_models.py`
- New columns on `WorldServerInstance` (all `Text`, default `""`):
  - `ac_path`, `build_path` — per-instance AzerothCore source and build directories.
  - `char_db_host`, `char_db_port`, `char_db_user`, `char_db_password`, `char_db_name` — per-instance characters database.
  - `soap_host`, `soap_port`, `soap_user`, `soap_password` — per-instance SOAP endpoint.

##### `backend/app/core/database.py`
- `run_panel_db_migrations()` extended to ADD the 11 new columns (v1.2 block)
  to existing databases — safe to run on every startup.
- New `get_char_db_for_instance(instance_id)` async generator: looks up the
  instance's `char_db_*` overrides and returns a session to the correct database.
  Falls back to global `AC_CHAR_DB_*` settings when no overrides are set.

##### `backend/app/models/schemas.py`
- `WorldServerInstanceSchema`, `WorldServerInstanceCreate`, `WorldServerInstanceUpdate`
  all extended with the 11 new optional override fields.
- `SqlQueryRequest.instance_id` — scopes the characters DB session.
- `BuildConfig`: added `ac_path`, `build_path`, `process_name` optional fields.

#### Backend — API changes

##### `backend/app/api/v1/endpoints/instances.py`
- `_enrich()` now includes all 11 override fields in the serialised response.
- `create_instance` and `update_instance` persist the override fields.
- `instance_command` — routes via `execute_command_for_instance` when
  `soap_user`/`soap_password` are set on the instance; otherwise falls back to
  daemon stdin.

##### `backend/app/api/v1/endpoints/database.py`
- Added `_db_session(database, instance_id)` async context manager — central
  routing helper that picks the right session factory per database type.
- All endpoints (`/tables`, `/query`, `/table`, `/backup`) now accept
  `instance_id` query parameter (or request-body field for POST endpoints).
- `/backup` resolves per-instance `char_db_*` credentials when `instance_id`
  is supplied, and now correctly uses `AC_WORLD_DB_*` credentials (previously
  all non-auth databases incorrectly used `AC_AUTH_DB_*`).

##### `backend/app/api/v1/endpoints/players.py`
- `GET /players/characters` and `GET /players/characters/{guid}` accept
  `instance_id` query parameter; routes via `get_char_db_for_instance`.
- Switched import from removed `get_char_db` to `get_char_db_for_instance`.

##### `backend/app/api/v1/endpoints/logs.py`
- `/sources`, `/{source}`, `/{source}/size`, `/{source}/download` all accept
  `instance_id` query parameter and forward it to the log manager.

##### `backend/app/api/v1/endpoints/modules.py`
- `GET /modules/installed`, `POST /modules/install`, `DELETE /modules/{name}`,
  `POST /modules/{name}/update`, `POST /modules/update-all`,
  `POST /modules/update-azerothcore` all accept an `ac_path` override (query
  param or request-body field) to target a specific AC installation.

##### `backend/app/api/v1/endpoints/compilation.py`
- `POST /compilation/build` forwards `ac_path_override`, `build_path_override`,
  and `process_name` to `run_build`.

##### `backend/app/services/azerothcore/compiler.py`
- `run_build()` accepts `ac_path_override`, `build_path_override`, `process_name`.
- **Phase 5** (new): after a successful build, when `process_name` is set and
  differs from `"worldserver"`, creates a relative symlink
  `bin/<process_name> → worldserver` (falls back to `shutil.copy2` if symlinks
  are unsupported).

##### `backend/app/services/azerothcore/soap_client.py`
- New `execute_command_for_instance(command, instance_id)` — resolves
  per-instance SOAP overrides before sending the command; falls back to global
  settings gracefully.

#### Frontend

##### `frontend/src/types/index.ts`
- `WorldServerInstance`, `WorldServerInstanceCreate`, `WorldServerInstanceUpdate`
  extended with 11 override fields.
- New `BuildConfig` interface with `ac_path`, `build_path`, `process_name`.

##### `frontend/src/services/api.ts`
- `logsApi` — all functions accept optional `instanceId`.
- `playersApi.characters` and `.character` accept optional `instanceId`.
- `dbApi.tables`, `.query`, `.browse`, `.backup` accept optional `instance_id`.
- `compileApi.build` accepts optional `acPath`, `buildPath`, `processName`.
- `modulesApi.installed`, `.install`, `.remove`, `.updateAzerothCore`,
  `.updateModule`, `.updateAll` accept optional `acPath`.
- `instancesApi` CRUD methods pass all new override fields.

##### `frontend/src/pages/ServerControl.tsx`
- `InstanceModal` — new *Per-Instance Overrides* collapsible section with
  fields for `ac_path`, `build_path`, characters DB, and SOAP credentials.
  Collapsed by default; toggle with `ChevronDown`/`ChevronUp`.

##### `frontend/src/pages/Compilation.tsx`
- Instance selector (hidden when only one instance) targets the build at a
  specific instance's `ac_path` / `build_path` / `process_name`.

##### `frontend/src/pages/DatabaseManager.tsx`
- Instance selector (characters DB only; hidden when one instance) routes all
  DB queries/browsing/backup to the selected instance's character database.

##### `frontend/src/pages/LogViewer.tsx`
- Instance selector routes log tail, search, download, and live WebSocket
  stream to the selected instance's log directory.

##### `frontend/src/pages/ModuleManager.tsx`
- Instance selector routes installed list, install, remove, and all update
  operations to the selected instance's AC installation path.

##### `frontend/src/pages/PlayerManagement.tsx`
- Instance selector on the characters tab routes character queries to the
  selected instance's character database.

---

### Added – Structured Application Logging

##### `backend/app/main.py`
- `logging.basicConfig` configured at startup with two handlers:
  - **Stream** (`sys.stdout`) — for Docker container log capture.
  - **RotatingFileHandler** — writes to `$PANEL_LOG_DIR/panel.log` (default
    `/data/logs/panel.log`); rotates at 10 MB, keeps 5 files (≤ 50 MB total).
- Log format: `YYYY-MM-DD HH:MM:SS [module] LEVEL  message`.
- Noisy third-party libraries (`httpx`, `httpcore`, `uvicorn.access`) set to
  `WARNING` to reduce noise.
- New HTTP middleware logs every request: `METHOD /path → STATUS (ms)`.

Every backend module now uses `logger = logging.getLogger(__name__)` and logs:
- Notable user actions (login, start/stop, ban, kick, modify, config save …).
- Every compilation, installation, and build start/completion.
- Errors and warnings from SOAP, database, and external processes.
- JWT validation failures and authentication events.
- Settings updates (sensitive values redacted).

---

### Changed

#### `docker-compose.yml`
- `panel_data` named Docker volume replaced with **`./data` host-mount**.
  The SQLite database and application logs are now written to `./data/` in
  the project directory — directly accessible on the host without `docker exec`.
- `volumes:` top-level section: `panel_data:` entry removed.

#### `frontend/src/hooks/useWebSocket.ts`
- Fixed URL construction: `?token=…` is now appended with `?` or `&`
  depending on whether the path already contains a query string (needed by
  `LogViewer` when passing `instance_id` in the WS path).

---

### Fixed

#### `backend/app/api/v1/endpoints/database.py`
- Backup endpoint previously used `AC_AUTH_DB_*` credentials for the  
  `characters` and `world` databases, causing backup failures when those
  databases live on different hosts or use different credentials.  Each
  database now correctly uses its own `AC_*_DB_*` settings.

#### `backend/app/api/v1/endpoints/instances.py`
- `generate-config` endpoint now sets a unique `LogsDir` in the generated
  `worldserver.conf` (per-instance subdirectory under the logs root) so
  worldserver log files from different instances do not overwrite each other.
- `generate-config` auto-populates `binary_path` and `working_dir` on the
  instance when the AC binary path is known, removing the manual step of
  setting these fields after config generation.
- `RealmName` key now applied via the config patch dict (was previously not
  included in overrides).

---

## [1.3.0] – 2026-03-01

### Summary of changes in this release

| Area | Change |
|---|---|
| **Multi-worldserver instances** | Run any number of independent worldserver processes from a single panel — full CRUD, per-instance start/stop/restart/console, and live status polling |
| **In-panel worldserver provisioning** | Create a second (or third) worldserver entirely from the UI: 2-step wizard generates a patched `worldserver.conf` with custom ports, realm name and realm ID |
| **Per-instance config editor** | Each instance card now has a **Config** tab — load, edit and save that instance's `worldserver.conf` without leaving the panel |
| **Panel self-update** | New Settings UI + `make version` / `make update` + host-daemon commands to pull from GitHub and rebuild containers without shell access |
| **AzerothCore source updates** | `POST /modules/update-azerothcore` streams `git pull` output; surfaced as a **Pull Latest Source** card on the Compilation page |
| **Module git updates** | Per-module and bulk `git pull` from Module Manager → Installed tab |
| **UX** | Moved AC source update from Module Manager to the Compilation page (natural pull → compile workflow) |
| **Playerbots DB** | Auto-detected `acore_playerbots` tab in Database Manager when `mod-playerbots` is installed |
| **Host daemon** | TCP daemon (`127.0.0.1:7879`) manages game-server processes outside Docker so they survive container restarts |

---

### Added – Multi-Worldserver Instances & In-Panel Configuration Provisioning

The panel can now manage an unlimited number of worldserver processes and
provision each one's configuration file directly from the UI.

#### Backend — data model & migrations

##### `backend/app/models/panel_models.py`
- New `WorldServerInstance` SQLAlchemy model: `id`, `display_name`,
  `process_name` (unique daemon key), `binary_path`, `working_dir`,
  `conf_path` (path to this instance's `worldserver.conf`), `notes`,
  `sort_order`.

##### `backend/app/models/schemas.py`
- `WorldServerInstanceSchema`, `WorldServerInstanceCreate`,
  `WorldServerInstanceUpdate`, `WorldServerInstanceListResponse` — full
  Pydantic schema set for instance CRUD.
- New `WorldServerProvisionRequest` schema: `conf_output_path`, `realm_name`,
  `worldserver_port`, `instance_port`, `ra_port`, `realm_id`,
  `extra_overrides`.

##### `backend/app/core/database.py`
- `run_panel_db_migrations()` — `PRAGMA table_info`-based runtime migration
  that adds `conf_path` to existing `worldserver_instances` tables so
  upgrades are non-destructive.

##### `backend/app/main.py`
- Lifespan now calls `run_panel_db_migrations()` before seeding defaults so
  the column is available on first boot after upgrade.

#### Backend — API endpoints

##### `backend/app/api/v1/endpoints/instances.py` *(new file)*
- `GET    /server/instances` — list all instances with live process status.
- `POST   /server/instances` — create a new instance.
- `GET    /server/instances/{id}` — fetch one instance.
- `PUT    /server/instances/{id}` — update metadata.
- `DELETE /server/instances/{id}` — stop process (if running) then delete.
- `POST   /server/instances/{id}/start|stop|restart` — process control.
- `POST   /server/instances/{id}/command` — send a GM console command via
  the host daemon's `console` channel.
- `GET    /server/instances/{id}/config` — read the instance's
  `worldserver.conf`; falls back to the global `AC_WORLDSERVER_CONF`.
- `PUT    /server/instances/{id}/config` — write updated conf content.
- `POST   /server/instances/{id}/generate-config` — copy the global
  `worldserver.conf` as a template, apply regex-based key=value patches
  (ports, realm name, realm ID), write to `conf_output_path`, and update
  the instance's `conf_path` in the DB.

##### `backend/app/services/azerothcore/instance_seeder.py` *(new file)*
- Seeds a default `"worldserver"` instance on first startup so the main
  server appears without manual configuration.

##### `backend/app/services/azerothcore/server_manager.py`
- `start_instance` and `restart_instance` now accept `conf_path` and pass
  `-c <conf_path>` to the daemon when set.

##### `backend/ac_host_daemon.py`
- `_do_start` / `_handle_client` extended to accept an `args` list and
  spread it into the subprocess call, enabling per-instance `--config`
  flag support.

#### Frontend

##### `frontend/src/types/index.ts`
- `WorldServerInstance` extended with `conf_path`.
- New `WorldServerProvisionRequest` interface.

##### `frontend/src/services/api.ts`
- `instancesApi` extended with `getConfig(id)`, `saveConfig(id, content)`,
  `generateConfig(id, data)`.

##### `frontend/src/hooks/useServerStatus.ts`
- Full hook set: `useInstances`, `useStartInstance`, `useStopInstance`,
  `useRestartInstance`, `useCreateInstance`, `useUpdateInstance`,
  `useDeleteInstance`.

##### `frontend/src/pages/ServerControl.tsx`
- **Authserver** card unchanged.
- **Worldserver Instances** grid: each `InstanceCard` now has a two-tab
  layout — **Status** (live stats + start/stop/restart + GM console) and
  **Config** (lazy-loaded conf editor with Save/Discard).
- **Add Instance** modal is now a 2-step wizard:
  - *Step 1* — display name, process name, binary path, working dir, notes.
    Process name auto-fills the suggested conf output path.
  - *Step 2* — optional "Generate a `worldserver.conf`" toggle; when
    enabled exposes `conf_output_path`, `realm_name`, `realm_id`,
    `worldserver_port`, `instance_port`, `ra_port` fields.  On submit the
    instance is created and the config is generated in one flow.
- Provision errors surfaced inline above the instances grid.

---

### Changed – AzerothCore Source Update Relocated to Compilation Page

The "Pull Latest Source" action is now surfaced on the **Compilation** page
as a prominent card above the build configuration, replacing its previous
location buried in Module Manager → Installed tab.  The natural workflow
is *pull source → compile*, and placing both on the same page makes that
obvious.

#### `frontend/src/pages/Compilation.tsx`
- Added **Pull Latest Source** card at the top of the page.
- Streams `POST /modules/update-azerothcore` output inline (expandable log
  area), identical UX pattern to the existing build-output section.
- Imports: `GitPullRequest`, `ArrowUpCircle`, `ChevronDown`, `ChevronUp`
  from lucide-react; `modulesApi` from `@/services/api`.

#### `frontend/src/pages/ModuleManager.tsx`
- Removed the AzerothCore source update card from the Installed tab to
  eliminate duplication (feature now lives on the Compilation page).
- Removed now-unused `GitPullRequest` import.

---

### Added – AzerothCore Source & Module Updates

The Module Manager can now pull the latest code for the AzerothCore source
tree and for any installed module directly from the panel — no SSH or shell
access required.

#### `backend/app/services/azerothcore/module_manager.py`
- Added `update_azerothcore(ac_path)` — `git pull --rebase` +
  `git submodule update --init --recursive` for the AzerothCore source tree.
  Streams output line-by-line as an async generator.
- Added `update_module(module_name, modules_path)` — same pull + submodule
  update for a single installed module directory.
- Added `update_all_modules(modules_path)` — iterates every sub-directory
  that contains a `.git` folder and runs the same sequence, collecting per-module
  success/failure. Non-git directories are silently skipped.
- All three functions validate that the target directory exists and has a `.git`
  folder before attempting any git operation.

#### `backend/app/api/v1/endpoints/modules.py`
- Added `POST /modules/update-azerothcore` — SSE stream of the source-tree
  update. Reads `AC_PATH` from panel settings.
- Added `POST /modules/{module_name}/update` — SSE stream for a single module.
  Includes path-traversal guard.
- Added `POST /modules/update-all` — SSE stream for all git-tracked modules.
- All three endpoints return `text/event-stream` with the same `{"line": str}`
  / `{"done": true}` SSE protocol used by the install and compilation endpoints.

#### `frontend/src/services/api.ts`
- Added `modulesApi.updateAzerothCore(signal?)` — `POST /modules/update-azerothcore`.
- Added `modulesApi.updateModule(moduleName, signal?)` — `POST /modules/{name}/update`.
- Added `modulesApi.updateAll(signal?)` — `POST /modules/update-all`.

#### `frontend/src/pages/ModuleManager.tsx`
- `LogPanel` component generalised: `moduleTitle` prop renamed to `title`;
  header no longer hardcodes "Installing:" — callers pass the complete label.
- Added `handleUpdate` — generic SSE stream handler shared by all three update
  actions (AC source / single module / all modules). Mirrors the existing
  `handleInstall` pattern.
- **Installed tab** now contains:
  - **AzerothCore Source** card with an **Update AzerothCore Source** button,
    link to the Compilation page, and a brief explanation.
  - **Update All Modules** button beside the Refresh button; disabled when no
    git-tracked modules are installed or an update is already running.
  - Per-module **Update** button (shown only for git-tracked modules); disabled
    while any update is running to prevent concurrent git operations.
- Update log output renders in the same full-screen `LogPanel` modal as install
  output. Closing the modal invalidates the `modules-installed` query so the
  list re-fetches fresh state.

---

### Added – Panel Self-Update

AzerothPanel can now update itself from the GitHub repository with a single
command or button click — no manual `git pull` + rebuild dance required.

#### `backend/ac_host_daemon.py`
- Added `version` daemon command — fetches origin tags silently, returns current
  `commit`, `branch`, `version` (from `git describe`), and `commits_behind`
  (number of commits HEAD is behind `origin/HEAD`).
- Added `update` daemon command — runs `git pull --rebase` then
  `docker compose up --build -d` in the project directory from the **host**,
  so the real source tree is updated and the containers are rebuilt/restarted
  correctly. Project directory is auto-detected from `__file__` (no config).
- `_run_cmd()` helper — thin asyncio wrapper around `create_subprocess_exec`
  with combined stdout+stderr capture and a 600-second timeout (sufficient for
  Docker rebuilds).

#### `backend/app/api/v1/endpoints/settings.py`
- Added `GET /api/v1/settings/panel-version` — proxies the daemon `version`
  command; returns version metadata as JSON. Returns HTTP 503 when the daemon
  is unreachable.
- Added `POST /api/v1/settings/update-panel` — proxies the daemon `update`
  command with a 660-second timeout to allow for full Docker image rebuilds.
  Returns HTTP 503 when the daemon is unreachable; HTTP 500 on update failure
  with the error detail from the daemon.

#### `frontend/src/services/api.ts`
- Added `settingsApi.panelVersion()` — `GET /settings/panel-version`.
- Added `settingsApi.updatePanel()` — `POST /settings/update-panel`.

#### `frontend/src/pages/Settings.tsx`
- New **Panel Update** section (above GitHub Integration) with:
  - **Check for Updates** button — displays current version tag, branch, commit
    hash, and a colour-coded "N commit(s) behind origin" / "Up to date" badge.
  - **Update Panel** button — triggers `POST /settings/update-panel`; shows
    scrollable git pull + Docker compose output in a collapsible log panel on
    completion or error.
- Imports `DownloadCloud`, `GitBranch`, `Tag` from `lucide-react`.

#### `Makefile`
- Added `make version` — prints tag, branch, commit, and upstream lag from git.
- Added `make update` — `git pull --rebase` then `docker compose up --build -d`.
- Both targets included in `help` output and `.PHONY`.

---

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
