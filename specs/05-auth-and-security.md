# 05 - Auth and Security

## Authentication
- Passwords: argon2id (`argon2-cffi`), min length 8, reject top common passwords.
- Access token: JWT HS256 (switch to RS256 if a second service verifies tokens), 15 min, claims `sub, role, jti, exp`. Held in memory in the SPA.
- Refresh token: 256-bit random, only its SHA-256 stored. Cookie `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth`. 30-day expiry, rotated on each use. Reuse of a rotated token revokes the whole `family_id`.
- Lockout: 5 failures -> `locked_until` +10 minutes (exponential on repeats). Same error text for unknown user and bad password.
- Rate limits (per IP and per identifier): login 10/min, register 5/hour, payment submit 10/hour.
- CSRF: refresh endpoint uses SameSite cookie plus a custom header check (`X-Requested-With`); all other endpoints use bearer tokens, so no cookie-based CSRF surface.

## Authorisation (RBAC + tenant scoping)
| Resource | CUSTOMER | OPERATOR (member) | ADMIN |
|---|---|---|---|
| Public catalog | read | read | read |
| Own bookings | CRUD own | n/a | read all |
| Operator's packages/departures | none | OWNER/STAFF manage | suspend/unsuspend |
| Operator's bookings | none | own operator only | read all, manual create |
| Operator docs / NID | none | upload own, never read back | view via signed URL (audit) |
| Operator members, payout methods | none | OWNER only | read |
| Offers | read | none | CRUD |
| Audit logs | none | none | read |

Implementation rules:
1. FastAPI dependencies: `require_role(...)`, `current_operator_member()` which resolves `operator_id` from `operator_members` for the session user.
2. Repository methods for operator data **require** an `operator_id` argument; there is no unscoped variant.
3. Return 404 (not 403) when a resource belongs to another tenant.
4. A `pytest` fixture creates two operators; every operator endpoint has a test that operator B cannot read or change operator A's data.

## Sensitive data
- NID number: encrypt with Fernet/AES-GCM using `NID_ENCRYPTION_KEY`; duplicate check with HMAC-SHA256 using `NID_HASH_KEY`; display only last 4. Keys separate from the DB, rotated by re-encryption script.
- Documents in a **private** bucket; admin access only through 60-second signed URLs; each issuance written to `audit_logs`.
- Never log passwords, tokens, NID, full phone numbers (mask), or payment txn ids in plain logs.

## Input and platform hardening
- Validate all inputs with Pydantic; enforce max lengths; sanitise rich text (render descriptions as plain text or sanitised markdown).
- Uploads: allow-list MIME (jpeg, png, webp, pdf), max 5 MB, re-encode images, random storage keys.
- CORS allow-list from `CORS_ORIGINS`; security headers (HSTS, `X-Content-Type-Options`, frame denial) via middleware and Vercel config.
- Dependency scanning in CI (`pip-audit`, `npm audit`).
- Admin seeding via CLI: `python -m app.cli create-admin --email ...`; never through the API.

## Threat checklist for reviews
IDOR across operators, privilege escalation on signup, overbooking race, replayed booking request, payment txn id reuse, forged operator approval, NID leakage via API or logs, public bucket exposure, refresh-token theft.
