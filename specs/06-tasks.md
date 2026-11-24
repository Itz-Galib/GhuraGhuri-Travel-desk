# 06 - Task Plan for Coding Agents

Rules: one task per session or PR; follow `AGENTS.md` Definition of Done; tick when merged. Spec refs in brackets.

## Phase 0 - Foundations
- [ ] T0.1 Repo scaffold, docker-compose (api + postgres), ruff/mypy/pytest, GitHub Actions CI. [02]
- [ ] T0.2 Config (`pydantic-settings`), DB session, Alembic baseline, error envelope, request-id middleware, `/health`. [04]
- [ ] T0.3 Frontend scaffold: Vite + TS, Tailwind, router with `/`, `/operator`, `/admin` areas, API client with token refresh, OpenAPI type generation. [02]

## Phase 1 - Identity
- [ ] T1.1 Migrations: users, refresh_tokens. Register/login/refresh/logout/me with rotation, lockout, rate limits. [05, US-A1, US-A2]
- [ ] T1.2 RBAC dependencies, admin seed CLI, role-guarded frontend routes, login/register pages. [05, C4]
- [ ] T1.3 Tests: auth flows, token reuse revocation, privilege-escalation attempt. [05]

## Phase 2 - Operators and verification
- [ ] T2.1 Migrations: operators, operator_members, verification_documents, audit_logs. [03]
- [ ] T2.2 Operator onboarding API + storage port (S3) + NID encryption/hash utilities with unit tests. [05, US-A3]
- [ ] T2.3 Admin operator review API + signed URLs + audit logging. [US-E1]
- [ ] T2.4 Frontend: operator onboarding wizard; admin review screen. [US-A3, US-E1]
- [ ] T2.5 Cross-tenant test fixture (two operators). [05]

## Phase 3 - Catalog
- [ ] T3.1 Migrations: tour_packages, images, departures, offers. [03]
- [ ] T3.2 Operator package + departure CRUD, publish rules, capacity guard. [US-D1, US-D2]
- [ ] T3.3 Public catalog: list/filter/detail, date availability search, offers. [US-B1 to B4]
- [ ] T3.4 Frontend: operator package editor and departures; public browse, detail, date search. [US-B*, US-D*]

## Phase 4 - Booking core
- [ ] T4.1 Migrations: bookings, travellers, events, payments, idempotency_keys, notifications. [03]
- [ ] T4.2 Booking state machine module + unit tests for every transition. [01]
- [ ] T4.3 Create booking with atomic seat reservation + idempotency; concurrency test (50 parallel requests for 5 seats -> exactly 5 succeed). [US-C1, A3]
- [ ] T4.4 Sweeper job: expire holds, release seats; reconciliation CLI for invariant 1. [A4]
- [ ] T4.5 Dummy payment submission, operator verify/reject, confirm/reject booking. [US-C2, US-D4]
- [ ] T4.6 Cancellation request/decision; departure bulk-cancel. [US-C4, A7]
- [ ] T4.7 Frontend: booking flow, payment form, my bookings with timeline, operator booking queue. [US-C*, D3, D4]

## Phase 5 - Admin and channel edge cases
- [ ] T5.1 Manual booking (operator + admin) with source FACEBOOK/PHONE/WALK_IN. [US-D5, US-E4, A5]
- [ ] T5.2 Notify-unavailable action + notifications API + message text. [US-E5, A6]
- [ ] T5.3 Admin bookings list, filters, CSV export; package moderation; offers CRUD; audit viewer. [US-E2, E3, E6]
- [ ] T5.4 Dashboards (operator, admin). [US-D6, E7]
- [ ] T5.5 Frontend admin panel screens for the above + in-app notifications UI. [US-C5]

## Phase 6 - Hardening and release
- [ ] T6.1 Security review against the 05 threat checklist; add missing tests. [05]
- [ ] T6.2 Seed script with realistic Bangladesh demo data (Sajek, Sylhet tea gardens, Cox's Bazar, Sundarbans). 
- [ ] T6.3 Dockerfile (prod), Render + Neon + Vercel deploy, env docs, README with architecture diagram.
- [ ] T6.4 Smoke test script against deployed URL; Lighthouse mobile check.

## Deferred (v1.1 / v2) - do not build now
Phone OTP verification, SMS/WhatsApp/Facebook webhooks via ChannelAdapter, real payment gateway behind PaymentProvider, chatbot for availability queries, reviews, coupon codes, flight and hotel portals (`booking_items` migration), queue worker.

## Spec questions (agents append here)
- 
