# GhuraGhuri Travel Desk

A tour-booking marketplace for Bangladesh: verified tour operators publish dated
departures, customers reserve seats, and admins verify operators and oversee
bookings. v1 covers tours only.

The full contract lives in [`specs/`](./specs) and [`AGENTS.md`](./AGENTS.md).
If code and spec disagree, the spec wins.

## Stack

| Layer | Technology |
| --- | --- |
| API | Python 3.12, FastAPI, SQLAlchemy 2 (typed), Alembic, Pydantic v2 |
| Database | PostgreSQL 16 (Neon in production) |
| Web | React 18, Vite, TypeScript, React Router, TanStack Query, Tailwind |
| Deploy | Docker / Render (API), Neon (DB), Vercel (web) |

```
[React SPA] /  /operator  /admin
      |  HTTPS JSON /api/v1
[FastAPI modular monolith]
      |                         |
[PostgreSQL (Neon pooled)]   [private/public object storage]
      ^
[sweeper: expire unpaid holds]
```

## Repository layout

```
backend/
  app/
    api/            versioned router (/api/v1)
    core/           config, db, errors, middleware, logging
    modules/        auth users operators tours departures bookings payments ...
  alembic/          migrations (baseline 0001)
  tests/
frontend/
  src/
    app/            providers, router, layout
    features/       tours, operator, admin, auth
    lib/api/        fetch client with in-memory token + refresh, generated types
specs/              00 decisions ... 06 tasks
neon.ts             Neon branch/services policy (managed by `neon deploy`)
```

## Local development

Prerequisites: Python 3.12, Node 22, Docker (for PostgreSQL).

```bash
# 1. Start PostgreSQL
docker compose up -d postgres

# 2. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Or run both services in Docker: `docker compose up --build`. The API is at
<http://localhost:8000>, docs at `/docs`, liveness at `/health`, DB readiness at
`/health/ready`.

```bash
# 3. Frontend
cd frontend
npm install
npm run dev            # http://localhost:5173, proxies /api to :8000
```

Copy `.env.example` to `.env` for the API and `frontend/.env.example` to
`frontend/.env.local` for the web app. Never commit real secrets.

## Environment

`backend/app/core/config.py` is the source of truth. Important variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | pooled Neon connection string used by the app |
| `DATABASE_URL_UNPOOLED` | direct connection string used by Alembic |
| `JWT_SECRET` | access-token signing key (T1) |
| `CORS_ORIGINS` | comma-separated allowed origins |
| `BOOKING_HOLD_MINUTES` | unpaid hold window (default 30) |
| `NID_ENCRYPTION_KEY`, `NID_HASH_KEY` | operator NID encryption / duplicate hash (T2) |
| `STORAGE_*` | S3-compatible buckets for photos and private documents (T2) |
| `VITE_API_URL` | API origin for the web app |

## Neon

This repo is linked to the Neon project `muddy-block-52137380` (branch
`production`). `neon deploy` applies [`neon.ts`](./neon.ts) and pulls the
pooled/unpooled Postgres URLs into `.env.local`.

```bash
neon login
neon deploy
cd backend && alembic upgrade head
```

The app uses the pooled URL with `pool_pre_ping=True`; migrations use the
unpooled URL (spec 00 E3). `.env.local` is git-ignored.

## Quality gates

```bash
cd backend && ruff check . && ruff format --check . && mypy app && pytest
cd frontend && npm run lint && npm run typecheck && npm run build
```

CI runs the same gates against a PostgreSQL service container, including an
Alembic upgrade/downgrade check.

## API types

FastAPI is the schema source of truth. With the API running:

```bash
cd frontend
npm run gen:api    # writes src/lib/api/schema.d.ts from /openapi.json
```

`src/lib/api/schema.d.ts` is a placeholder until the first feature endpoints
land; regenerate it rather than hand-writing DTOs.
