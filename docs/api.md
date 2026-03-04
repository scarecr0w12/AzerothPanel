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
| `GET` | `/status` | Worldserver & authserver running status, online player count |
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
| `lines` | `int` | Number of tail lines to return (default `100`) |

---

### Database Manager — `/api/v1/database`

![Database Manager page](screenshots/database.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tables/{database}` | List tables in a database (`auth`, `world`, `characters`) |
| `POST` | `/query` | Execute a SQL query (read-only safety check enforced) |
| `GET` | `/table/{database}/{table_name}` | Browse a table with pagination |
| `POST` | `/backup` | Initiate a database backup (mysqldump) |

#### `POST /api/v1/database/query`

```json
{
  "database": "world",
  "query": "SELECT entry, name FROM creature_template LIMIT 10"
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

#### `POST /api/v1/compilation/build`

```json
{
  "cmake_options": "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
  "cores": 4
}
```

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
| `GET` | `/installed` | List locally installed modules |
| `POST` | `/install` | Clone and install a module by repository slug |
| `DELETE` | `/{module_name}` | Remove an installed module |

---

### Config Editor — `/api/v1/configs`

![Config Editor page](screenshots/config_editor.png)

| Method | Path | Description |
|---|---|---|
| `GET` | `/files` | List all editable `.conf` files |
| `GET` | `/files/{filename}` | Get the raw text content of a config file |
| `PUT` | `/files/{filename}` | Save updated content to a config file |

---

### Backup & Restore — `/api/v1/backup`

#### Destinations

| Method | Path | Description |
|---|---|---|
| `GET` | `/destinations` | List all configured backup destinations |
| `POST` | `/destinations` | Create a new backup destination |
| `GET` | `/destinations/{id}` | Get a single destination |
| `PUT` | `/destinations/{id}` | Update a destination |
| `DELETE` | `/destinations/{id}` | Delete a destination |
| `POST` | `/destinations/{id}/test` | Test connectivity / credentials |
| `GET` | `/destinations/{id}/files` | List archive files stored at the destination |

##### Supported destination types

| `type` | Provider | Required config fields |
|---|---|---|
| `local` | Local filesystem | `path` |
| `sftp` | SFTP | `host`, `port`, `username`, `password` (or `private_key`), `path` |
| `ftp` | FTP / FTPS | `host`, `port`, `username`, `password`, `path`, `use_tls` |
| `s3` | AWS S3 / S3-compatible | `bucket`, `region`, `access_key`, `secret_key`, `prefix` (opt), `endpoint_url` (opt) |
| `gdrive` | Google Drive | `credentials_json`, `folder_id` |
| `onedrive` | Microsoft OneDrive | `client_id`, `client_secret`, `tenant_id`, `folder_path` |

##### `POST /api/v1/backup/destinations`

```json
{
  "name": "Daily S3",
  "type": "s3",
  "config": {
    "bucket": "my-ac-backups",
    "region": "us-east-1",
    "access_key": "AKIA...",
    "secret_key": "..."
  },
  "enabled": true
}
```

#### Jobs

| Method | Path | Description |
|---|---|---|
| `GET` | `/jobs` | List all backup jobs |
| `GET` | `/jobs/{id}` | Get a single job |
| `DELETE` | `/jobs/{id}` | Delete a job record |
| `GET` | `/jobs/{id}/files` | List archive files associated with a job |
| `DELETE` | `/jobs/{id}/files/{filename}` | Delete a specific archive file |

#### Run & Restore (SSE streams)

| Method | Path | Description |
|---|---|---|
| `POST` | `/run` | Start a new backup (SSE stream) |
| `POST` | `/restore` | Restore from a completed backup job (SSE stream) |

##### `POST /api/v1/backup/run`

```json
{
  "destination_id": 1,
  "include_configs": true,
  "include_databases": true,
  "include_server_files": false,
  "notes": "pre-update snapshot"
}
```

The response is an **SSE stream** of progress lines. A `BackupJob` record is created immediately (status `running`) and updated to `completed` or `failed` when the stream ends.  Config files from secondary worldserver instances (stored at arbitrary paths) are automatically included under `configs/instances/{name}/`.

##### `POST /api/v1/backup/restore`

```json
{
  "job_id": 42,
  "restore_configs": true,
  "restore_databases": true,
  "restore_server_files": false
}
```

The response is an **SSE stream** of restore progress. The job must be in `completed` status. Per-instance config files are written back to their original absolute paths.

---

## WebSocket — Live Log Streaming

```
ws://<host>/ws/logs/{source}
```

Opens a persistent WebSocket connection that streams new log lines in real time as they are appended to the log file. Each message is a plain-text log line.

### Example (JavaScript)

```javascript
const ws = new WebSocket("ws://localhost/ws/logs/worldserver");
ws.onmessage = (event) => console.log(event.data);
```

---

## Health Check

```http
GET /health
```

Returns `{"status": "ok"}` with HTTP 200. No authentication required. Used by Docker health checks and load balancers.
