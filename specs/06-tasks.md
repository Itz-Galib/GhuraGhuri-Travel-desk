# 06 - Task Plan for Coding Agents

Rules: one task per session or PR; follow `AGENTS.md` Definition of Done; tick when merged. Spec refs in brackets.

## Phase 0 - Foundations
- [x] T0.1 Repo scaffold, docker-compose (api + postgres), ruff/mypy/pytest, GitHub Actions CI. [02]
- [x] T0.2 Config (`pydantic-settings`), DB session, Alembic baseline, error envelope, request-id middleware, `/health`. [04]
- [x] T0.3 Frontend scaffold: Vite + TS, Tailwind, router with `/`, `/operator`, `/admin` areas, API client with token refresh, OpenAPI type generation. [02]

## Phase 1 - Identity
- [x] T1.1 Migrations: users, refresh_tokens. Register/login/refresh/logout/me with rotation, lockout, rate limits. [05, US-A1, US-A2]
- [x] T1.2 RBAC dependencies, admin seed CLI, role-guarded frontend routes, login/register pages. [05, C4]
- [x] T1.3 Tests: auth flows, token reuse revocation, privilege-escalation attempt. [05]

## Phase 2 - Operators and verification
- [x] T2.1 Migrations: operators, operator_members, verification_documents, audit_logs. [03]
- [x] T2.2 Operator onboarding API + storage port (S3) + NID encryption/hash utilities with unit tests. [05, US-A3]
- [x] T2.3 Admin operator review API + signed URLs + audit logging. [US-E1]
- [x] T2.4 Frontend: operator onboarding wizard; admin review screen. [US-A3, US-E1]
- [x] T2.5 Cross-tenant test fixture (two operators). [05]

## Phase 3 - Catalog
- [x] T3.1 Migrations: tour_packages, images, departures, offers. [03]
- [x] T3.2 Operator package + departure CRUD, publish rules, capacity guard. [US-D1, US-D2]
- [x] T3.3 Public catalog: list/filter/detail, date availability search, offers. [US-B1 to B4]
- [x] T3.4 Frontend: operator package editor and departures; public browse, detail, date search. [US-B*, US-D*]

## Phase 4 - Booking core
- [x] T4.1 Migrations: bookings, travellers, events, payments, idempotency_keys, notifications. [03]
- [x] T4.2 Booking state machine module + unit tests for every transition. [01]
- [x] T4.3 Create booking with atomic seat reservation + idempotency; concurrency test (50 parallel requests for 5 seats -> exactly 5 succeed). [US-C1, A3]
- [x] T4.4 Sweeper job: expire holds, release seats; reconciliation CLI for invariant 1. [A4]
- [x] T4.5 Dummy payment submission, operator verify/reject, confirm/reject booking. [US-C2, US-D4]
- [x] T4.6 Cancellation request/decision; departure bulk-cancel. [US-C4, A7]
- [x] T4.7 Frontend: booking flow, payment form, my bookings with timeline, operator booking queue. [US-C*, D3, D4]

## Phase 5 - Admin and channel edge cases
- [x] T5.1 Manual booking (operator + admin) with source FACEBOOK/PHONE/WALK_IN. [US-D5, US-E4, A5]
- [x] T5.2 Notify-unavailable action + notifications API + message text. [US-E5, A6]
- [x] T5.3 Admin bookings list, filters, CSV export; package moderation; offers CRUD; audit viewer. [US-E2, E3, E6]
- [x] T5.4 Dashboards (operator, admin). [US-D6, E7]
- [x] T5.5 Frontend admin panel screens for the above + in-app notifications UI. [US-C5]

## Phase 6 - Hardening and release
- [x] T6.1 Security review against the 05 threat checklist; add missing tests. [05]
- [x] T6.2 Seed script with realistic Bangladesh demo data (Sajek, Sylhet tea gardens, Cox's Bazar, Sundarbans).
- [x] T6.3 Dockerfile (prod), Render + Neon + Vercel deploy, env docs, README with architecture diagram.
- [x] T6.4 Smoke test script against deployed URL; Lighthouse mobile check.

## Deferred (v1.1 / v2) - do not build now
Phone OTP verification, SMS/WhatsApp/Facebook webhooks via ChannelAdapter, real payment gateway behind PaymentProvider, chatbot for availability queries, reviews, coupon codes, flight and hotel portals (`booking_items` migration), queue worker.

## Spec questions (agents append here)
- 2026-11-25 (T0): `00` B2 lists `operator_members` roles `OWNER/MANAGER/STAFF`, but the `03` contract CHECK allows only `OWNER/STAFF`. Implementing `03`; please confirm whether `MANAGER` is needed.
- 2026-11-25 (T0): `00` A1 specifies uniqueness on `(operator_id, trx_id)`, while `03` defines `payments` without `operator_id` and a unique index on `(provider, provider_txn_id)`. Following `03`; TrxID replay protection will be verified against this in T4.5.
- 2026-11-25 (T0): `00` A8 describes structured cancellation-policy presets, while `03` declares `tour_packages.cancellation_policy` as free `text`. Following `03`; presets would need a migration.
- 2026-11-25 (T0): `00` A10 adds minimal post-trip ratings, but `AGENTS.md`/`01` scope has no reviews and `03` has no ratings table. Treating ratings as out of scope for v1.
