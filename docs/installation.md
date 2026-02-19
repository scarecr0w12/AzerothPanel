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
| Python | 3.11+ | **Only** for the manual (no-Docker) path |
| Node.js | 20 LTS | **Only** for the manual (no-Docker) path |

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

# CORS (set false + populate CORS_ORIGINS for production hardening)
CORS_ALLOW_ALL=true
```

### 3. Start

```bash
make docker-up
# equivalent to:
docker compose up --build -d
```

The panel is available at `http://<your-host>:80` (or `PANEL_PORT`).

### 4. First login

1. Open the panel URL in your browser.
2. Log in with the credentials from `PANEL_ADMIN_USER` / `PANEL_ADMIN_PASSWORD`.
3. Go to **Settings** and fill in:
   - AzerothCore installation path (pre-filled with `AC_PATH` value)
   - MySQL connection details for auth, world, and characters databases
   - SOAP connection details
4. Click **Test Connection** to verify, then **Save**.

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

```bash
git pull
make docker-restart
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
