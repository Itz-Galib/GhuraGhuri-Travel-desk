# 04 - API Contract (v1)

Base path `/api/v1`. JSON. Auth: `Authorization: Bearer <access_jwt>`. Refresh via cookie. Dates ISO 8601. Money in poisha (integers).

## Conventions
- Pagination: `?page=1&page_size=20` (max 100) -> `{ "items": [...], "page": 1, "page_size": 20, "total": 134 }`
- Error envelope: `{ "error": { "code": "SEATS_UNAVAILABLE", "message": "...", "details": {...}, "request_id": "..." } }`
- Status codes: 400 validation (422 from Pydantic mapped to 400 envelope), 401 unauthenticated, 403 forbidden, 404 not found (also used to hide other tenants' resources), 409 state/availability conflict, 429 rate limited.
- `Idempotency-Key` header required on `POST /bookings`.

## Auth
| Method | Path | Notes |
|--------|------|-------|
| POST | /auth/register | customer signup |
| POST | /auth/login | returns access token, sets refresh cookie |
| POST | /auth/refresh | rotates refresh cookie |
| POST | /auth/logout | revokes refresh family |
| GET | /me | profile, role, operator memberships |
| PATCH | /me | update name/phone/email |

## Public / customer
| Method | Path | Notes |
|--------|------|-------|
| GET | /tours | filters: `destination, date_from, date_to, min_price, max_price, duration, q, sort` |
| GET | /tours/{slug} | detail with upcoming departures and active offers |
| GET | /departures | `date=2026-12-26&destination=Sajek` availability search |
| GET | /offers | active offers |
| POST | /bookings | `{departure_id, seats, contact_name, contact_phone, travellers[]}` -> 201 |
| GET | /bookings | mine |
| GET | /bookings/{id} | mine, includes timeline and payments |
| POST | /bookings/{id}/payments | `{provider, amount, sender_number, provider_txn_id}` |
| POST | /bookings/{id}/cancel-request | `{reason}` |
| GET | /notifications | mine; `POST /notifications/{id}/read` |

## Operator (role OPERATOR, scoped to the user's operator)
| Method | Path | Notes |
|--------|------|-------|
| POST | /operator/profile | create operator application |
| POST | /operator/documents | multipart upload (NID front/back, selfie, note) |
| POST | /operator/submit | DRAFT -> PENDING |
| POST/GET | /operator/members | owner only |
| GET/POST | /operator/tours | list, create |
| GET/PATCH | /operator/tours/{id} | edit |
| POST | /operator/tours/{id}/publish | requires APPROVED operator |
| POST | /operator/tours/{id}/archive | |
| POST/GET | /operator/tours/{id}/departures | |
| PATCH | /operator/departures/{id} | capacity >= seats_booked |
| POST | /operator/departures/{id}/cancel | bulk cancel flow |
| GET | /operator/bookings | filters `status, departure_id` |
| POST | /operator/bookings | manual booking |
| POST | /operator/payments/{id}/verify | `{approve: bool, reason}` |
| POST | /operator/bookings/{id}/confirm or /reject | |
| POST | /operator/bookings/{id}/cancel-decision | `{approve: bool}` |
| GET | /operator/dashboard | |

## Admin (role ADMIN)
| Method | Path | Notes |
|--------|------|-------|
| GET | /admin/operators | filter by verification status |
| GET | /admin/operators/{id} | no raw NID; shows last4 |
| GET | /admin/operators/{id}/documents/{doc_id}/url | signed URL, 60 s, audit-logged |
| POST | /admin/operators/{id}/approve / reject / suspend | `{reason}` |
| GET | /admin/bookings | filters, `?format=csv` export |
| POST | /admin/bookings | manual booking on behalf of customer (`source=FACEBOOK`) |
| POST | /admin/bookings/{id}/notify-unavailable | cancels, releases seats, creates notification + returns message text |
| POST | /admin/bookings/{id}/flag | needs_attention toggle |
| POST | /admin/tours/{id}/suspend / unsuspend | `{reason}` |
| CRUD | /admin/offers | |
| GET | /admin/audit-logs | |
| GET | /admin/dashboard | |

## Health
`GET /health` (liveness) and `GET /health/ready` (DB check).

## Schema source of truth
FastAPI generates OpenAPI at `/openapi.json`. The frontend generates its API types from it (`openapi-typescript`); do not hand-write DTOs.
