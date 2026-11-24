# 00 - Loopholes Analysis and Decisions (v1: User + Tour Operator + Admin)

Each row is a gap in the original plan, plus the decision this spec makes. Agents must follow the decisions. Items marked OPEN need the product owner.

## A. Business and product gaps
| # | Gap | Decision for v1 |
|---|-----|-----------------|
| A1 | Business model unclear: who holds the advance money? | **Platform records, does not hold, money in v1.** Advance goes to the operator's bKash/Nagad number; operator or admin verifies it. Each operator has `commission_bps` (stored, unused until v2). OPEN: confirm commission-on-booking vs subscription. |
| A2 | "Tour package" mixes the product with a dated trip. "Day tour on 26 Dec" cannot be answered. | Split into **TourPackage** (template) and **Departure** (date, price, capacity). Users book departures. |
| A3 | Overbooking: two users book the last seat. | Atomic seat reservation in one SQL statement (see 03). Never read-then-write in app code. |
| A4 | Unpaid bookings hold seats forever. | Booking starts `PENDING_PAYMENT` with `expires_at` (default 30 min). A sweeper expires it and releases seats. |
| A5 | Facebook-confirmed bookings have no home in the data model. | Admin/operator can create a **manual booking** with `source=facebook`, contact name + phone, and no user account. Same state machine as web bookings. |
| A6 | Package becomes unavailable after Facebook confirmation. | Booking state `CANCELLED_UNAVAILABLE` + admin action "notify unavailable". v1 notification = in-app record + copyable message text. SMS/WhatsApp in v2. |
| A7 | Operator deletes or edits a package with live bookings. | Packages are never hard-deleted (status `ARCHIVED`). Cancelling a departure with active bookings requires a bulk-cancel flow that marks each booking and creates notifications. Price edits never change existing bookings (price snapshot). |
| A8 | Refund and cancellation rules are undefined. | Each package has `cancellation_policy` text. v1 refunds are manual: admin marks payment `REFUNDED` with a note. No automated refunds. |
| A9 | Discounts undefined. | Simple `offers` (percent or flat, date range, one package). Booking snapshots the final price and the offer id. No coupon codes in v1. |
| A10 | Who may review or rate? | Out of scope for v1. |

## B. Identity, trust and verification
| # | Gap | Decision |
|---|-----|----------|
| B1 | Fake operators and scams are the biggest platform risk. | Operators cannot publish until `verification_status=APPROVED` by an admin. Unverified operators may draft only. |
| B2 | Facebook groups and "authorised members" are not modelled. | `operators` is an organisation (type `INDIVIDUAL` or `GROUP`). Users join via `operator_members` (roles `OWNER`, `STAFF`). Group verification needs the owner's NID plus an authorisation note. |
| B3 | NID is highly sensitive PII. | Store NID number encrypted (app-level), plus a keyed hash for duplicate detection and last 4 digits for display. Images live in private storage, served via short-lived signed URLs, never public. Only admins can view. Log every view in `audit_logs`. |
| B4 | One person registers many fake operator accounts. | Unique constraint on NID hash and on operator phone. Admin can suspend. |
| B5 | Phone numbers unverified. | v1: collect and format-validate (+8801XXXXXXXXX). OTP verification is a v1.1 task behind a `PhoneVerifier` interface. |

## C. Authentication and authorisation
| # | Gap | Decision |
|---|-----|----------|
| C1 | One login for everyone or three? | **One `users` table, one login, role-based access** (`CUSTOMER`, `OPERATOR`, `ADMIN`). Portals are route areas guarded by role. |
| C2 | Token storage in browser. | Access JWT (15 min) kept in memory; refresh token in `HttpOnly; Secure; SameSite=Lax` cookie, rotated on use, stored hashed server-side, revocable. |
| C3 | Operator A reads or edits operator B's data (IDOR). | Every operator query is scoped by `operator_id` derived from the session, never from the request body. Automated cross-tenant tests are mandatory. |
| C4 | Self-registration as ADMIN. | Public signup creates `CUSTOMER` only. `OPERATOR` is granted via operator onboarding. `ADMIN` only via CLI seed command. |
| C5 | Brute force and enumeration. | Rate limit login and signup, generic error messages, argon2id hashing, lockout backoff. |

## D. Data integrity and scaling
| # | Gap | Decision |
|---|-----|----------|
| D1 | Money as floats. | Integer minor units (poisha) in `BIGINT`, currency column fixed to `BDT`. |
| D2 | Time zones. | Store UTC `timestamptz`; trip dates are `date`. Display in Asia/Dhaka. |
| D3 | Double submit creates two bookings. | `Idempotency-Key` header on booking creation, unique per user. |
| D4 | Status as free text. | PostgreSQL enums or checked text + one state-machine module; illegal transitions raise errors. |
| D5 | Future flight/hotel portals will clash with tour tables. | Operator org and members are generic. Product tables are tour-specific (`tour_*`). Bookings reference `departure_id` now; v2 adds a generic `booking_items` layer. See 02. |
| D6 | No audit trail. | `audit_logs` for admin and operator state changes. |
| D7 | Schema drift across agents. | Alembic migrations only. Agents never edit the DB by hand. |
| D8 | Search and filter slow later. | Indexes on (status, start_date), (destination), trigram search later. Cursor or offset pagination on every list endpoint. |

## E. Operations
| # | Gap | Decision |
|---|-----|----------|
| E1 | Image uploads. | S3-compatible storage (Cloudflare R2 or Supabase Storage). Type and size validation. Public package photos vs private NID docs in separate buckets. |
| E2 | Background work (expiry, notifications). | v1: a single scheduled sweeper (APScheduler inside the API, or a cron-invoked CLI command). v2: queue worker. |
| E3 | Free-tier cold starts and DB limits. | Use Neon pooled connection string; `/health` endpoint; document cold-start behaviour. |
| E4 | Secrets leak. | `.env` only, `.env.example` committed, never commit real secrets. |
| E5 | Bangladesh data protection and consent. | Terms and privacy consent checkbox at signup; store `consented_at`. |

## OPEN questions for the product owner
1. Commission vs subscription (A1). Default: record-only, commission field stored.
2. Does the operator or the admin verify advance payments? Default: operator verifies, admin can override.
3. Is cancelling by users allowed in v1? Default: user may request cancellation, operator or admin approves.
4. Language: English only, or Bangla too? Default: English UI, i18n-ready strings.
