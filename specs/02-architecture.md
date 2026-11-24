# 02 - Architecture

## Style
Modular monolith: one FastAPI service, one Postgres, one React SPA with three role-guarded areas. Split into services only when a module has independent scaling or team ownership.

```
[React SPA]  /            customer area (public + logged in)
             /operator    operator portal  (role OPERATOR)
             /admin       admin panel      (role ADMIN)
      |  HTTPS, JSON, /api/v1
[FastAPI]  auth | users | operators | tours | departures | bookings
           payments | offers | notifications | admin | audit
      |                               |
[PostgreSQL (Neon)]            [Object storage: public photos, private NID docs]
      ^
[Sweeper job: expire holds, every minute]
```

## Why this scales to flights and hotels later
- `users`, `operators`, `operator_members`, `verification_documents`, `payments`, `notifications`, `audit_logs` are **domain-neutral**. A hotel or airline is another `operators.kind`.
- Tour-specific tables are prefixed `tour_` / `departures`. In v2 add `hotel_*` and `flight_*` product tables.
- v1 `bookings.departure_id` is the only tour-coupled column. In v2, introduce `booking_items(booking_id, product_type, product_id, ...)` and migrate. Keep all booking logic behind `bookings/service.py` so this migration touches one module.
- Channels (web, facebook, phone) are a `source` enum plus a `ChannelAdapter` interface; a Facebook/WhatsApp webhook adapter later creates bookings through the same service.

## Key design patterns
- **Repository + service** per module; services own the DB transaction (one transaction per request).
- **Atomic seat reservation** (inside the booking transaction):
  ```sql
  UPDATE departures
     SET seats_booked = seats_booked + :n
   WHERE id = :id AND status = 'OPEN' AND seats_booked + :n <= capacity
  RETURNING id;
  ```
  Zero rows returned -> `SEATS_UNAVAILABLE`. Release uses `seats_booked = seats_booked - :n` inside the same transaction as the status change.
- **Idempotency:** `idempotency_keys(user_id, key, request_hash, response_body)` unique on (user_id, key).
- **Pluggable ports:** `PaymentProvider`, `NotificationSender`, `FileStorage`, `PhoneVerifier`. v1 implementations: manual payment, in-app notifications, S3 storage, no-op verifier.
- **Error envelope and request id** middleware; structured JSON logs.

## Environments and deployment
| Env | Backend | DB | Frontend |
|-----|---------|----|----------|
| local | docker-compose (api + postgres) | local postgres | `vite dev` |
| prod | Render (Docker) | Neon (pooled URL for app, direct URL for Alembic) | Vercel |

Config via env: `DATABASE_URL`, `DATABASE_URL_DIRECT`, `JWT_SECRET`, `REFRESH_COOKIE_DOMAIN`, `CORS_ORIGINS`, `NID_ENCRYPTION_KEY`, `NID_HASH_KEY`, `STORAGE_*`, `BOOKING_HOLD_MINUTES=30`.
Cross-site cookies: if frontend and API are on different registrable domains, use a shared custom domain or a Vercel rewrite proxying `/api` to Render so the refresh cookie stays first-party.

## CI (GitHub Actions)
Lint, type check, tests against a Postgres service container, migration up/down check, frontend build.
