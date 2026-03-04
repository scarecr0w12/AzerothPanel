# Configuration Reference

AzerothPanel has two configuration layers:

1. **Environment variables** — loaded at container/process start from `.env` files. Required before the panel can run.
2. **In-panel Settings** — stored in the SQLite database. Editable at runtime through the **Settings** page. No restart required.

---

## Environment Variables

### `backend/.env`

| Variable | Default | Required | Description |
|---|---|---|---|
| `SECRET_KEY` | — | **Yes** | HS256 signing key for JWT tokens. Generate with `openssl rand -hex 32`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | No | JWT lifetime in minutes (default 24 h). |
| `PANEL_ADMIN_USER` | `admin` | No | Panel login username. |
| `PANEL_ADMIN_PASSWORD` | `admin` | **Yes** | Panel login password. **Change before first run.** |
| `PANEL_DB_URL` | `sqlite+aiosqlite:///./panel.db` | No | SQLAlchemy URL for the panel's own SQLite database. In Docker, set to `sqlite+aiosqlite:////data/panel.db` so data persists in the named volume. |
| `CORS_ALLOW_ALL` | `true` | No | When `true`, CORS allows any origin. Set `false` for production hardening. |
| `CORS_ORIGINS` | — | No | JSON array of allowed origins, e.g. `["http://192.168.1.10"]`. Only used when `CORS_ALLOW_ALL=false`. |

### `.env` (Docker Compose)

| Variable | Default | Description |
|---|---|---|
| `AC_PATH` | `/opt/azerothcore` | Absolute path to the AzerothCore installation on the **host** machine. Bind-mounted into the backend container. |
| `PANEL_PORT` | `80` | Host port the panel frontend is exposed on. |

---

## In-Panel Settings (Settings Page)

These values are stored in the panel's SQLite database and applied at runtime. No restart is needed after saving.

![Settings page](screenshots/settings.png)

### AzerothCore

| Field | Description |
|---|---|
| **AC Path** | Absolute path to the AzerothCore directory (same as `AC_PATH`). Used by the compiler, installer, and server manager. |
| **Build Dir** | CMake build directory relative to AC Path (default `build`). |
| **Data Dir** | Path to the `Data` directory with client files (default `<AC_PATH>/data`). |
| **Worldserver Binary** | Path to the `worldserver` executable (default `<AC_PATH>/bin/worldserver`). |
| **Authserver Binary** | Path to the `authserver` executable (default `<AC_PATH>/bin/authserver`). |

### MySQL — Auth Database

| Field | Description |
|---|---|
| **Host** | MySQL hostname (default `127.0.0.1`). |
| **Port** | MySQL port (default `3306`). |
| **User** | MySQL username with access to the auth database. |
| **Password** | MySQL password. |
| **Database** | Auth database name (usually `acore_auth`). |

### MySQL — World Database

Same fields as Auth Database. Database name is usually `acore_world`.

### MySQL — Characters Database

Same fields as Auth Database. Database name is usually `acore_characters`.

### SOAP

| Field | Description |
|---|---|
| **Host** | SOAP host (default `127.0.0.1`). Must match `SOAP.IP` in `worldserver.conf`. |
| **Port** | SOAP port (default `7878`). Must match `SOAP.Port` in `worldserver.conf`. |
| **User** | In-game account with GM level 3 used for SOAP commands. |
| **Password** | Password for the SOAP account. |

---

## Security Hardening Checklist

- [ ] Set `SECRET_KEY` to a unique 32+ byte random value.
- [ ] Change `PANEL_ADMIN_PASSWORD` from the default `admin`.
- [ ] Set `CORS_ALLOW_ALL=false` and list explicit origins if the panel is reachable from untrusted machines.
- [ ] Place the panel behind a TLS-terminating reverse proxy (nginx, Caddy) if accessed over the internet.
- [ ] Restrict MySQL user permissions — the panel only needs read/write on `acore_auth`, `acore_characters`, and read on `acore_world`; it does NOT need `GRANT`, `CREATE`, or `DROP` privileges.
- [ ] Do **not** expose port 8000 (backend API) directly to the network; let nginx proxy it.
