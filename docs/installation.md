# Installation Guide

This guide covers every supported way to install and run AzerothPanel.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker (recommended)](#docker-recommended)
3. [Manual (without Docker)](#manual-without-docker)
4. [Reverse proxying behind an existing web server](#reverse-proxying-behind-an-existing-web-server)
5. [Updating the panel](#updating-the-panel)
6. [Uninstalling](#uninstalling)

---

## Prerequisites

### Required on the host machine

| Component | Minimum version | Notes |
|---|---|---|
| AzerothCore | Any recent release | Must be compiled and installed on the host |
| MySQL / MariaDB | MySQL 5.7 / MariaDB 10.3 | Already required by AzerothCore |
| Docker Engine | 24.x | Only for the Docker path |
| Docker Compose | v2.x (`docker compose`) | Only for the Docker path |
| Python | 3.11+ | Required for the host daemon (`ac_host_daemon.py`) and the manual dev path |
| Node.js | 20 LTS | **Only** for the manual (no-Docker) dev path |

### AzerothCore SOAP

The server-control and player-management features rely on the SOAP interface built into worldserver. Enable it in `worldserver.conf`:

```ini
SOAP.Enabled = 1
SOAP.IP      = 127.0.0.1
SOAP.Port    = 7878
```

Create a GM account for the panel (the account used in Settings > SOAP):

```sql
-- In the `auth` database
INSERT INTO account (username, sha_pass_hash, ...) VALUES ('panelsoap', ...);
-- or via worldserver console:
account create panelsoap <password>
account set gmlevel panelsoap 3 -1
```

---

## Docker (recommended)

### 1. Clone

```bash
git clone https://github.com/scarecr0w12/AzerothPanel.git
cd AzerothPanel
```

### 2. Environment files

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

**`.env`** — Docker Compose variables:

```dotenv
# Absolute path to your AzerothCore installation on the HOST machine
AC_PATH=/opt/azerothcore

# Path to your WoW 3.3.5a client (for data extraction from local client)
# Leave as default if you don't have a client (use download method instead)
CLIENT_PATH=/root/clientdata

# Port the panel is exposed on (change if 80 is already in use)
PANEL_PORT=80
```

**`backend/.env`** — Application secrets:

```dotenv
# Generate: openssl rand -hex 32
SECRET_KEY=replace_with_long_random_string

# Panel login credentials
PANEL_ADMIN_USER=admin
PANEL_ADMIN_PASSWORD=change_me

# SQLite panel database (leave as-is for Docker)
PANEL_DB_URL=sqlite+aiosqlite:////data/panel.db

# Host daemon TCP address (daemon runs on the host; backend uses network_mode: host)
AC_DAEMON_HOST=127.0.0.1
AC_DAEMON_PORT=7879
```

### 3. Start the host daemon

> **Why this matters:** The panel backend runs inside a Docker container. If the
> game servers were managed as container subprocesses they would be killed every
> time you restart or update the panel. The host daemon runs outside Docker and
> owns the AzerothCore processes, so they survive container restarts.

```bash
# Option A — quick background process (runs until next reboot)
make daemon-start

# Option B — install as a systemd service (auto-starts on every boot, recommended)
sudo make daemon-install
```

Confirm the daemon is up:

```bash
make daemon-status
# → Daemon running (PID 12345)
# { "services": [{"name": "worldserver", "running": false}, ...] }
```

The daemon will now be the parent of any worldserver / authserver process that
the panel starts. Restarting or rebuilding the Docker containers will not affect
running game servers.

### 4. Start the panel

```bash
make docker-up
# equivalent to:
docker compose up --build -d
```

The panel is available at `http://<your-host>:80` (or `PANEL_PORT`).

### 5. First login

1. Open the panel URL in your browser.
2. Log in with the credentials from `PANEL_ADMIN_USER` / `PANEL_ADMIN_PASSWORD`.

   ![AzerothPanel login screen](screenshots/login.png)

3. After a successful login you will land on the **Dashboard**, which shows real-time worldserver / authserver status.

   ![Dashboard overview](screenshots/dashboard.png)

4. Go to **Settings** and fill in:
    - AzerothCore installation path (pre-filled with `AC_PATH` value)
    - MySQL connection details for auth, world, and characters databases
    - SOAP connection details

   ![Settings page](screenshots/settings.png)

5. Click **Save Settings** to apply. Changes take effect immediately — no restart required.

### 6. Client Data Extraction

Before starting the servers, you need client data files (DBC, Maps, VMaps, MMaps). Go to **Data Extraction** in the sidebar:

![Data Extraction page](screenshots/data_extraction.png)

**Option A: Download Pre-Extracted Data (Recommended)**
- Click "Download Data" to fetch pre-extracted data from AzerothCore releases (~1.5GB)
- Takes 2-10 minutes depending on your connection
- No WoW client required

**Option B: Extract from Local Client**
- If you have a World of Warcraft 3.3.5a (12340) client installed
- Set `CLIENT_PATH` in your `.env` file to point to your WoW client directory
- The path is mounted read-only into the Docker container
- Select which data types to extract in the Data Extraction page
- Note: MMaps generation takes 30-60 minutes

Once data extraction is complete, you can start the servers from the **Server Control** page.

![Server Control page](screenshots/server_control.png)

---

## Manual (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set SECRET_KEY, PANEL_ADMIN_USER, PANEL_ADMIN_PASSWORD

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # dev server on :5173 with HMR
# OR
npm run build      # production build to dist/
```

In development mode the Vite proxy in `vite.config.ts` forwards `/api/` and `/ws/` to `localhost:8000`.

For a production-like setup without Docker, serve `frontend/dist/` with any static file server (e.g. nginx) and proxy `/api/` and `/ws/` to `:8000`.

### Convenience shortcut

```bash
make install   # install both backend & frontend deps
make dev       # start both concurrently (requires make 4.x)
```

---

## Reverse proxying behind an existing web server

If you already run nginx or Caddy on port 80, set `PANEL_PORT` to an unprivileged port (e.g. `8080`) in `.env` and add an upstream block:

### nginx

```nginx
server {
    listen 443 ssl;
    server_name panel.example.com;

    ssl_certificate     /etc/ssl/certs/panel.crt;
    ssl_certificate_key /etc/ssl/private/panel.key;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
    }

    location /ws/ {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 3600s;
    }
}
```

### Caddy

```
panel.example.com {
    reverse_proxy localhost:8080
}
```

---

## Updating the panel

There are three equivalent ways to update AzerothPanel to the latest version from GitHub.

### Option A — Panel UI (requires daemon)

1. Go to **Settings** in the sidebar.
2. Scroll to the **Panel Update** section.
3. Click **Check for Updates** to see how many commits behind origin you are.
4. Click **Update Panel** to pull and rebuild. A live output log is shown;
   the containers restart automatically when the build finishes.

> The host daemon must be running (`make daemon-start` / `make daemon-install`)
> for the UI update path to work, because `git pull` and `docker compose` must
> run on the host, not inside the container.

### Option B — Make target (on the host)

```bash
make version   # optional: check how far behind origin you are
make update    # git pull --rebase  →  docker compose up --build -d
```

### Option C — Manual steps

```bash
git pull --rebase
docker compose up --build -d
```

Database migrations run automatically on startup via SQLAlchemy `create_all`.

---

## Uninstalling

```bash
make docker-down
docker volume rm azerothpanel_panel_data   # removes the SQLite database
```

To also remove the cloned directory:

```bash
cd .. && rm -rf AzerothPanel
```
