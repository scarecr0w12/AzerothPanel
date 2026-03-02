# API Reference

The AzerothPanel backend exposes a versioned REST API and a WebSocket endpoint.

- **Base URL**: `http://<host>:8000`
- **API prefix**: `/api/v1`
- **Interactive docs (Swagger UI)**: `http://<host>:8000/docs`
- **Alternative docs (ReDoc)**: `http://<host>:8000/redoc`

The sections below describe each endpoint group alongside the corresponding panel UI.

---

## Authentication

All endpoints except `/api/v1/auth/login` and `/api/v1/auth/login/json` require a **JWT Bearer token**.

### Obtain a token

```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=your_password
```

```http
POST /api/v1/auth/login/json
Content-Type: application/json

{"username": "admin", "password": "your_password"}
```

Response:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### Use the token

Pass the token in the `Authorization` header on every subsequent request:

```
Authorization: Bearer eyJ...
```

---

## Endpoints

### Authentication — `/api/v1/auth`

| Method | Path | Description |
|---|---|---|
| `POST` | `/login` | Login via form body, returns JWT |
| `POST` | `/login/json` | Login via JSON body, returns JWT |
| `GET` | `/me` | Returns current user info |

---

### Server Control — `/api/v1/server`

![Server Control page](screenshots/server_control.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Worldserver & authserver running status, PID, CPU %, memory. Queries the host daemon when available; falls back to psutil when daemon is absent. |
| `POST` | `/worldserver/start` | Start the worldserver process |
| `POST` | `/worldserver/stop` | Stop the worldserver process |
| `POST` | `/worldserver/restart` | Restart the worldserver process |
| `POST` | `/authserver/start` | Start the authserver process |
| `POST` | `/authserver/stop` | Stop the authserver process |
| `POST` | `/authserver/restart` | Restart the authserver process |
| `POST` | `/command` | Execute an arbitrary GM command via SOAP |
| `GET` | `/info` | Server host information (CPU, memory, uptime) |
| `POST` | `/announce` | Send a global in-game announcement via SOAP |

#### `POST /api/v1/server/command`

```json
{ "command": "server info" }
```

Response:

```json
{ "result": "AzerothCore rev. ...\nConnected players: 3\n..." }
```

---

### Worldserver Instances — `/api/v1/server/instances`

Manage multiple independent worldserver processes from a single panel. Each instance has its own binary path, working directory, and `worldserver.conf`.

![Server Control page with instances](screenshots/server_control.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/server/instances` | List all instances with live process status |
| `POST` | `/server/instances` | Create a new instance |
| `GET` | `/server/instances/{id}` | Get one instance with live status |
| `PUT` | `/server/instances/{id}` | Update instance metadata |
| `DELETE` | `/server/instances/{id}` | Stop (if running) then delete the instance |
| `POST` | `/server/instances/{id}/start` | Start the instance's worldserver process |
| `POST` | `/server/instances/{id}/stop` | Stop the instance's worldserver process |
| `POST` | `/server/instances/{id}/restart` | Restart the instance's worldserver process |
| `POST` | `/server/instances/{id}/command` | Send a GM console command via the daemon stdin pipe |
| `GET` | `/server/instances/{id}/config` | Read this instance's `worldserver.conf`; falls back to global `AC_WORLDSERVER_CONF` |
| `PUT` | `/server/instances/{id}/config` | Write updated content to this instance's `worldserver.conf` |
| `POST` | `/server/instances/{id}/generate-config` | Copy the global conf as a template, patch ports/realm/ID, write to `conf_output_path` |

#### `POST /api/v1/server/instances` — Create instance

```json
{
  "display_name": "PTR Realm",
  "process_name": "worldserver-ptr",
  "binary_path": "/opt/azerothcore/bin/worldserver-ptr",
  "working_dir": "/opt/azerothcore/bin",
  "notes": "Public test realm",
  "ac_path": "/opt/azerothcore-ptr",
  "build_path": "/opt/azerothcore-ptr/build",
  "char_db_host": "127.0.0.1",
  "char_db_port": "3306",
  "char_db_user": "acore",
  "char_db_password": "acore",
  "char_db_name": "acore_characters_ptr",
  "soap_host": "127.0.0.1",
  "soap_port": "7879",
  "soap_user": "gm",
  "soap_password": "gmpassword"
}
```

All per-instance override fields (`ac_path`, `build_path`, `char_db_*`, `soap_*`) are optional and default to `""`.  An empty value means "use the global setting from the Settings page" — single-realm setups require no changes.

#### `POST /api/v1/server/instances/{id}/command` — Send a GM command

When the instance has `soap_user` / `soap_password` configured, the command is routed through that instance's SOAP endpoint. Otherwise it falls back to the daemon stdin pipe.

#### `POST /api/v1/server/instances/{id}/generate-config` — Provision a conf file

```json
{
  "conf_output_path": "/opt/azerothcore/etc/worldserver-ptr.conf",
  "realm_name": "PTR",
  "realm_id": 2,
  "worldserver_port": 8086,
  "instance_port": 8086,
  "ra_port": 3444
}
```

The endpoint copies the global `worldserver.conf` and patches the specified key=value pairs in-place (including `RealmName` and a unique per-instance `LogsDir`).  The instance's `conf_path`, `binary_path`, and `working_dir` are updated in the database.  If `AC_BINARY_PATH` is configured and `process_name` differs from `"worldserver"`, `binary_path` is set to `<AC_BINARY_PATH>/<process_name>` automatically.

---

### Player Management — `/api/v1/players`

![Player Management page](screenshots/players.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/online` | List currently online players (via SOAP) |
| `GET` | `/accounts` | List accounts with optional search/pagination |
| `GET` | `/characters` | List characters with optional search/pagination |
| `GET` | `/characters/{guid}` | Get a single character by GUID |
| `POST` | `/ban` | Ban an account by name with duration and reason |
| `POST` | `/unban/{account_id}` | Remove an account ban |
| `POST` | `/kick/{player_name}` | Kick an online player |
| `POST` | `/announce` | Send a message to all online players |
| `POST` | `/modify` | Modify a player's stats (level, gold, etc.) |

#### `GET /api/v1/players/characters`

Query parameters:

| Param | Type | Description |
|---|---|---|
| `search` | `string` | Filter by character name |
| `page` | `int` | Page number (default `1`) |
| `page_size` | `int` | Results per page (default `50`) |
| `online_only` | `bool` | Return only online characters (default `false`) |
| `instance_id` | `int` | Scope to a specific worldserver instance's character database |

`GET /characters/{guid}` also accepts `instance_id` as a query parameter.

#### `GET /api/v1/players/accounts`

Query parameters:

| Param | Type | Description |
|---|---|---|
| `search` | `string` | Filter by username |
| `page` | `int` | Page number (default `1`) |
| `per_page` | `int` | Results per page (default `20`) |

#### `POST /api/v1/players/ban`

```json
{
  "account_name": "badplayer",
  "duration": "30d",
  "reason": "Cheating"
}
```

---

### Logs — `/api/v1/logs`

![Log Viewer page](screenshots/log_viewer.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/sources` | List available log sources (worldserver, authserver, etc.) |
| `GET` | `/{source}` | Get last N lines of a log file |
| `GET` | `/{source}/size` | Get the file size of a log source |
| `GET` | `/{source}/download` | Download a log file as a file attachment |

#### `GET /api/v1/logs/{source}`

Query parameters:

| Param | Type | Description |
|---|---|---|
| `lines` | `int` | Number of tail lines to return (default `500`) |
| `level` | `string` | Filter by log level (`ERROR`, `WARN`, `INFO`, `DEBUG`) |
| `search` | `string` | Full-text search pattern (regex supported) |
| `instance_id` | `int` | Scope to a specific worldserver instance's log directory |

`/sources`, `/{source}/size`, and `/{source}/download` also accept `instance_id`.

---

### Database Manager — `/api/v1/database`

![Database Manager page](screenshots/database.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/available` | List queryable database targets (`auth`, `world`, `characters`; `playerbots` when `mod-playerbots` is installed) |
| `GET` | `/tables/{database}` | List tables in a database (`auth`, `world`, `characters`, `playerbots`) |
| `POST` | `/query` | Execute a SQL query (read-only safety check enforced) |
| `GET` | `/table/{database}/{table_name}` | Browse a table with pagination |
| `POST` | `/backup` | Initiate a database backup (mysqldump) |

> **Playerbots database**: The `playerbots` target is only included in `/available` (and accepted by all other endpoints) when `{AC_PATH}/modules/mod-playerbots` exists on disk. Requests using `playerbots` when the module is absent return HTTP 404.

#### Per-instance characters database

All database endpoints accept an optional `instance_id` query parameter (or request-body field for POST endpoints).  When supplied and the target database is `characters`, the panel uses that instance's `char_db_*` credential overrides instead of the global `AC_CHAR_DB_*` settings.  All other databases always use global credentials.

#### `GET /api/v1/database/tables/{database}`

Query parameters:

| Param | Type | Description |
|---|---|---|
| `instance_id` | `int` | Scope `characters` DB to a specific worldserver instance |

#### `POST /api/v1/database/query`

```json
{
  "database": "characters",
  "query": "SELECT guid, name, level FROM characters LIMIT 10",
  "instance_id": 2
}
```

> **Note**: Writes (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`) are rejected server-side.

---

### Installation — `/api/v1/installation`

![Installation & Setup page](screenshots/installation.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Latest installation step status |
| `POST` | `/run` | Start the AzerothCore data installation (SSE stream) |
| `GET` | `/config/worldserver` | Read `worldserver.conf` as key-value pairs |
| `PUT` | `/config/worldserver` | Write updated key-value pairs to `worldserver.conf` |
| `GET` | `/config/authserver` | Read `authserver.conf` as key-value pairs |
| `PUT` | `/config/authserver` | Write updated key-value pairs to `authserver.conf` |

The `/run` endpoint uses **Server-Sent Events (SSE)**. The client receives a stream of `data:` lines with installation progress until completion.

---

### Compilation — `/api/v1/compilation`

![Compilation page](screenshots/compilation.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Current or last build status (idle / running / success / failed) |
| `POST` | `/build` | Trigger a CMake build (SSE stream of compiler output) |

> **Pull Latest Source** — The Compilation page also exposes a "Pull Latest Source" button that calls `POST /modules/update-azerothcore` (see Module Manager below). The rationale is that pulling updated source and then rebuilding are sequential steps that belong on the same page.

#### `POST /api/v1/compilation/build`

```json
{
  "build_type": "RelWithDebInfo",
  "jobs": 4,
  "cmake_extra": "-DTOOLS_BUILD=all",
  "ac_path": "/opt/azerothcore-ptr",
  "build_path": "/opt/azerothcore-ptr/build",
  "process_name": "worldserver-ptr"
}
```

`ac_path` and `build_path` override the global AC_PATH / AC_BUILD_PATH for this build only. When `process_name` is set (and differs from `"worldserver"`), a `worldserver-ptr` symlink is created alongside the `worldserver` binary in the build's `bin/` directory — enabling the daemon to track the process independently.

The response is an **SSE stream** of build output lines.

---

### Data Extraction — `/api/v1/data-extraction`

![Data Extraction page](screenshots/data_extraction.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Get extraction status and data presence |
| `POST` | `/download` | Download pre-extracted data from AzerothCore releases (SSE stream) |
| `POST` | `/extract` | Extract data from local WoW 3.3.5a client (SSE stream) |
| `POST` | `/cancel` | Cancel any running extraction operation |

#### `GET /api/v1/data-extraction/status`

Returns the current extraction status and which data types are present:

```json
{
  "in_progress": false,
  "current_step": null,
  "progress_percent": 0,
  "started_at": null,
  "error": null,
  "data_path": "/opt/azerothcore/build/data",
  "has_dbc": true,
  "has_maps": true,
  "has_vmaps": true,
  "has_mmaps": true,
  "data_present": true
}
```

#### `POST /api/v1/data-extraction/download`

Downloads pre-extracted client data from AzerothCore GitHub releases. This is the recommended method.

Request body (optional):

```json
{
  "data_path": "/custom/data/path",  // Optional, uses AC_DATA_PATH from settings
  "data_url": "https://..."          // Optional, uses default AzerothCore release URL
}
```

The response is an **SSE stream** of progress lines.

#### `POST /api/v1/data-extraction/extract`

Extracts client data from a local World of Warcraft 3.3.5a (12340) client.

Request body:

```json
{
  "client_path": "/path/to/wow-client",
  "data_path": "/opt/azerothcore/build/data",  // Optional
  "binary_path": "/opt/azerothcore/build/bin", // Optional
  "extract_dbc": true,
  "extract_maps": true,
  "extract_vmaps": true,
  "generate_mmaps": false  // Off by default due to long generation time
}
```

The response is an **SSE stream** of extraction progress lines.

---

### Settings — `/api/v1/settings`

![Settings page](screenshots/settings.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `` | Get all current panel settings |
| `PUT` | `` | Update panel settings |
| `POST` | `/test-db` | Test a MySQL connection with the supplied credentials |
| `GET` | `/panel-version` | Return current git tag, branch, commit hash, and how many commits HEAD is behind `origin/HEAD`. Requires the host daemon. |
| `POST` | `/update-panel` | Pull the latest code from GitHub and rebuild + restart Docker containers via the host daemon (long-running, up to 660 s). Returns `{"success": bool, "output": str}`. |

#### `GET /api/v1/settings`

Response:

```json
{
  "ac_path": "/opt/azerothcore",
  "mysql_auth_host": "127.0.0.1",
  "mysql_auth_port": 3306,
  "mysql_auth_user": "acore",
  "mysql_auth_db": "acore_auth",
  "soap_host": "127.0.0.1",
  "soap_port": 7878,
  ...
}
```

---

### Module Manager — `/api/v1/modules`

![Module Manager page](screenshots/modules.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/catalogue` | List available modules from the AzerothCore GitHub catalogue |
| `GET` | `/installed` | List locally installed modules (`ac_path` query param to target a specific installation) |
| `POST` | `/install` | Clone and install a module (`ac_path` in body to target a specific installation) |
| `POST` | `/update-azerothcore` | `git pull` the AzerothCore source tree (`{"ac_path": "..."}` body to target a specific installation) (SSE stream) |
| `POST` | `/update-all` | `git pull` all installed git-tracked modules (`{"ac_path": "..."}` body) (SSE stream) |
| `POST` | `/{module_name}/update` | `git pull` a single installed module (`ac_path` query param) (SSE stream) |
| `DELETE` | `/{module_name}` | Remove an installed module (`ac_path` query param to target a specific installation) |

All path-mutating endpoints accept an `ac_path` override so you can manage modules for a secondary AC installation without changing the global Settings.

---

### Config Editor — `/api/v1/configs`

![Config Editor page](screenshots/config_editor.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/files` | List all editable `.conf` files |
| `GET` | `/files/{filename}` | Get the raw text content of a config file |
| `PUT` | `/files/{filename}` | Save updated content to a config file |

---

## WebSocket — Live Log Streaming

```
ws://<host>/ws/logs/{source}?token=<jwt>[&instance_id=<id>]
```

Opens a persistent WebSocket connection that streams new log lines in real time as they are appended to the log file.  Authentication is via the `token` query parameter (the same JWT returned by `/auth/login`).

| Query Param | Description |
|---|---|
| `token` | **Required.** JWT bearer token. |
| `instance_id` | Optional. Scope the stream to a specific worldserver instance's log directory. |

The client can send a JSON message to update the level filter at any time:

```json
{ "level": "ERROR" }
```

Set `level` to `null` to stream all lines.

### Example (JavaScript)

```javascript
const ws = new WebSocket("ws://localhost/ws/logs/worldserver?token=eyJ...&instance_id=2");
ws.onmessage = (event) => console.log(JSON.parse(event.data).line);
```

---

## Health Check

```http
GET /health
```

Returns `{"status": "ok"}` with HTTP 200. No authentication required. Used by Docker health checks and load balancers.
