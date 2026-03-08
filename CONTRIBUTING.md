# Contributing to AzerothPanel

Thank you for your interest in contributing! This guide covers everything you need to set up a local development environment, follow project conventions, and submit a pull request.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Project Structure](#project-structure)
5. [Making Changes](#making-changes)
6. [Validation Checklist](#validation-checklist)
7. [Submitting a Pull Request](#submitting-a-pull-request)
8. [Reporting Bugs](#reporting-bugs)
9. [Requesting Features](#requesting-features)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating you are expected to uphold it.

---

## Getting Started

### Prerequisites

| Tool | Minimum version |
|---|---|
| Git | 2.x |
| Docker & Docker Compose v2 | Latest stable |
| Node.js | 20 LTS |
| Python | 3.12 |
| AzerothCore (host-side) | Latest master |

---

## Development Setup

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/AzerothPanel.git
cd AzerothPanel
```

### 2. Configure environment files

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

### 3. Backend development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend development

```bash
cd frontend
npm install
npm run dev    # dev server on http://localhost:5173 with HMR
```

The Vite dev server proxies `/api` to `http://localhost:8000` and `/ws` to `ws://localhost:8000`.

### 5. Full stack with Docker

```bash
make docker-up    # build & start all containers
make docker-logs  # tail logs
make docker-down  # stop containers
```

---

## Project Structure

```
backend/app/
  api/v1/endpoints/   # one file per feature area (auth, server, players, …)
  core/               # config, database init, JWT security
  models/             # SQLAlchemy ORM models (panel_models.py) + Pydantic schemas
  services/           # business logic (server_manager, compiler, backup_manager, …)

frontend/src/
  pages/              # one .tsx file per panel page
  components/         # layout/ (Header, Sidebar) + ui/ (Button, Card, …)
  services/api.ts     # all axios HTTP calls
  store/index.ts      # Zustand global state
  types/index.ts      # shared TypeScript types
```

See [docs/development.md](docs/development.md) for a complete walkthrough.

---

## Making Changes

### Adding a backend endpoint

1. Create or extend a file in `backend/app/api/v1/endpoints/`.
2. Add any new Pydantic request/response schemas to `backend/app/models/schemas.py`.
3. Register the router in `backend/app/api/v1/router.py`.
4. If a new SQLite column is needed, add an `ALTER TABLE … ADD COLUMN IF NOT EXISTS` block in `backend/app/core/database.py:run_panel_db_migrations()`.

### Adding a Python dependency

```bash
source backend/.venv/bin/activate
pip install <package>
pip freeze > backend/requirements.txt
```

Commit the updated `requirements.txt`.

### Adding a frontend page

1. Create `frontend/src/pages/MyPage.tsx`.
2. Register the route in `frontend/src/App.tsx`.
3. Add a nav link in `frontend/src/components/layout/Sidebar.tsx`.
4. Add any new API helper functions to `frontend/src/services/api.ts`.
5. Add shared TypeScript types to `frontend/src/types/index.ts`.

### Style guidelines

- **TypeScript**: strict mode — all types must be explicit. No `any` unless unavoidable.
- **Python**: follow PEP 8; use async/await throughout; keep endpoint handlers thin (business logic lives in `services/`).
- **CSS**: Tailwind utility classes only — no custom CSS files unless unavoidable.
- Do **not** add docstrings, comments, or type annotations to code you didn't change.
- Do **not** add error handling for impossible code paths — trust framework guarantees.

---

## Validation Checklist

Run these before every commit. All must pass:

```bash
# TypeScript — must be zero errors
cd frontend && npx tsc --noEmit

# Frontend production build
cd frontend && npm run build

# Python syntax check (run from backend/ with venv active)
find app -name "*.py" | xargs python -m py_compile

# Docker Compose config
docker compose config --quiet
```

> **Note:** `npm run lint` is intentionally excluded — ESLint v9 is installed but has no config file. Do not run it.

---

## Submitting a Pull Request

1. Create a feature branch off `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Make your changes and validate (see above).
3. Commit with a clear, imperative message:
   ```
   feat: add player character export to CSV
   fix: prevent worldserver restart race condition
   docs: update backup configuration reference
   ```
4. Push and open a PR against `main`. Fill in the PR template completely.
5. Ensure the CI checks pass before requesting review.

---

## Reporting Bugs

Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml). Please include:

- Steps to reproduce
- Expected vs. actual behaviour
- Relevant log output (`make docker-logs`)
- Your environment (OS, Docker version, AzerothCore version)

---

## Requesting Features

Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml). Describe the problem you are solving, your proposed solution, and any alternatives you considered.
