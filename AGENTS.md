# AGENTS.md - Project Constitution (read first, every session)

You are a coding agent on a tour-booking platform. Read `specs/00` to `specs/06` before coding. If code and spec disagree, the spec wins; propose a spec change instead of silently diverging.

## Product in one line
A marketplace where verified tour operators publish tour packages with dated departures, customers book them, and admins verify operators and oversee bookings. v1 = tours only.

## Stack (fixed, do not swap)
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x (typed), Alembic, Pydantic v2, PostgreSQL (Neon), pytest, ruff, mypy.
- Frontend: React 18 + Vite + TypeScript, React Router, TanStack Query, React Hook Form + Zod, Tailwind CSS.
- Packaging: Docker (backend), docker-compose for local (api + postgres). Frontend on Vercel, backend on Render.

## Repo layout
```
/backend
  app/
    main.py
    core/          # config, security, db, errors, deps
    modules/
      auth/ users/ operators/ tours/ departures/ bookings/ payments/
      offers/ notifications/ admin/ audit/
      # each module: models.py schemas.py repository.py service.py router.py
    jobs/          # sweeper (expire bookings)
  alembic/
  tests/
/frontend
  src/
    app/ (router, providers)
    features/ (auth, tours, bookings, operator, admin)
    components/ lib/ (api client)
/specs
```

## Architecture rules
1. **Modular monolith.** Modules talk through service functions, never import another module's repository or models for writes.
2. **Layering:** router -> service -> repository -> DB. Routers contain no business logic. Services own transactions and state transitions.
3. **Authorisation in dependencies and services**, never only in the UI. Operator-scoped queries take `operator_id` from the session.
4. **Money** is integer poisha. **Time** is UTC. **IDs** are UUIDv7 or UUIDv4 (`uuid` columns).
5. **State machines** live in one place per aggregate (`bookings/state.py`). Illegal transition = `409`.
6. **No hard deletes** on tours, departures, bookings, payments, operators.
7. All list endpoints paginate. All write endpoints validate with Pydantic. Errors use the envelope in 04.
8. Every schema change = an Alembic migration with upgrade and downgrade.
9. No secrets in code. Config via `pydantic-settings` from env.

## Definition of Done (per task)
- Spec section referenced in the commit message (e.g. `Implements 01 US-B2`).
- Tests written and passing: happy path, validation failure, authorisation failure, and for operator data a cross-tenant denial test.
- `ruff`, `mypy`, `pytest`, and frontend `tsc --noEmit` + `eslint` pass.
- Migration applied cleanly on an empty DB.
- No TODOs left without a linked entry in `specs/06-tasks.md`.

## Working method
1. Pick the next unchecked task in `06-tasks.md`.
2. Restate acceptance criteria, list files you will touch.
3. Write failing tests, implement, run checks.
4. Tick the task, note any spec ambiguity under "Spec questions" in `06-tasks.md`.
Do not start the next task without ticking the current one. Do not expand scope beyond v1.

## Out of scope for v1
Flights, hotels, real payment gateways, chatbot, reviews, coupon codes, SMS/WhatsApp sending, automated refunds, multi-currency.
