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

Prerequisite: Docker with the Compose plugin. The Docker workflow does not
require Python or Node.js installed on the host.

```bash
# Start the frontend, API, and PostgreSQL
docker compose up --build
```

On a fresh database, apply the schema migrations in another terminal after
the services have started:

```bash
docker compose exec api alembic upgrade head
```

Then open:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- API documentation: <http://localhost:8000/docs>

Vite forwards browser `/api` and `/health` requests to the `api` Compose
service. The backend reloads on code changes, and the frontend hot reloads
through its mounted source directory.

Stop the containers with `docker compose down`. This keeps the persistent
PostgreSQL data volume; do not add `-v` if you want to retain the database.
The `postgres_data` volume is also preserved when containers are rebuilt.

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
| `VITE_API_URL` | Optional API origin; Docker Compose uses relative requests through the Vite proxy |

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
