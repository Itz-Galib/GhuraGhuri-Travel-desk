# 00 - Loopholes Analysis and Decisions (v1: User + Tour Operator + Admin)

Each row is a gap in the original plan, plus the decision this spec makes. Agents must follow the decisions.

## A. Business and product gaps

| # | Gap | Decision for v1 |
| --- | --- | --- |
| A1 | Business model unclear: who holds the advance money? | **Platform records, does not hold, money in v1.** Advance goes to the operator's bKash/Nagad number. Users submit a unique `trx_id` + sender phone; enforce a unique constraint on `(operator_id, trx_id)` to prevent TrxID replay. Operator verifies by default, with admin override. Each operator has `commission_bps` (default `0`, stored, unused until v2); log GMV on every confirmed booking. |
| A2 | "Tour package" mixes the product with a dated trip. "Day tour on 26 Dec" cannot be answered. | Split into **TourPackage** (template, itinerary, inclusions) and **Departure** (start/end dates, price, capacity, booking cutoff timestamp). Users book departures. |
| A3 | Overbooking: two users book the last seat. | Atomic seat reservation in one SQL statement (see 03): `UPDATE tour_departures SET booked_seats = booked_seats + :qty WHERE id = :id AND booked_seats + :qty <= capacity`. Never read-then-write in app code. |
| A4 | Unpaid bookings hold seats forever. | Booking starts `PENDING_PAYMENT` with `expires_at` (default 30 min). Compute live availability dynamically (`capacity - active_seats` where `status = CONFIRMED` OR `expires_at > NOW()`), backed by a sweeper that marks expired bookings `EXPIRED` and reconciles counts. |
| A5 | Facebook-confirmed bookings have no home in the data model. | Admin/operator can create a **manual booking** with `source=FACEBOOK`, contact name + phone, optional `trx_id`, and `user_id = NULL`. Follows the exact same state machine as web bookings. |
| A6 | Package becomes unavailable after Facebook confirmation. | Booking state `CANCELLED_UNAVAILABLE` + admin/operator action "notify unavailable". v1 notification = in-app record + pre-filled Bangla/English WhatsApp (`wa.me`) click-to-chat link and copyable message text. Automated SMS/WhatsApp API in v2. |
| A7 | Operator deletes or edits a package with live bookings. | Packages are never hard-deleted (status `ARCHIVED`). Price edits never change existing bookings (booking stores `unit_price_poisha` snapshot). Cancelling a departure with active bookings requires an atomic bulk-cancel flow that marks each booking and creates notifications. |
| A8 | Refund and cancellation rules are undefined. | Each package has a structured `cancellation_policy` preset (`FLEXIBLE`, `MODERATE`, `STRICT`) plus custom text. Users may request cancellation before the departure cutoff (auto-cancels if `PENDING_PAYMENT`; requires operator/admin approval if `CONFIRMED`). v1 refunds are manual: operator/admin marks payment `REFUNDED` with refund `trx_id` and note. |
| A9 | Discounts undefined. | Simple `offers` table (percent or flat poisha, date range, scoped to package or departure) with a floor check (`final_price >= 0`). Booking snapshots `final_price_poisha` and `offer_id`. No coupon codes in v1. |
| A10 | Who may review or rate? | Minimal post-trip rating (1–5 stars + short text) gated strictly to bookings in `COMPLETED` state. |

## B. Identity, trust and verification

| # | Gap | Decision |
| --- | --- | --- |
| B1 | Fake operators and scams are the biggest platform risk. | Operators cannot publish (`PUBLISHED`) until `verification_status=APPROVED` by an admin. Unverified operators may draft only. Approval requires verified payout number (bKash/Nagad) and NID check. |
| B2 | Facebook groups and "authorised members" are not modelled. | `operators` is an organisation (type `INDIVIDUAL` or `GROUP`). Users attach via `operator_members` (roles `OWNER`, `MANAGER`, `STAFF`). Group verification needs the owner's NID plus the Facebook Group URL and proof of group admin role. |
| B3 | NID is highly sensitive PII. | Store NID number encrypted at app level (AES-256-GCM), plus an HMAC-SHA256 keyed hash for duplicate detection and `nid_last4` for display. Images live in private storage, served via 5-minute signed URLs, never public. Only admins can view. Log every view in `audit_logs`. |
| B4 | One person registers many fake operator accounts. | Unique constraint on `nid_hash` and on operator payout phone. Admin `SUSPENDED` status immediately hides all active departures from public search and blocks new bookings. |
| B5 | Phone numbers unverified. | v1: collect and format-validate (`+8801[3-9]\d{8}`), and verify operator payout numbers manually during onboarding. Full SMS OTP verification is a v1.1 task behind a `PhoneVerifier` interface. |

## C. Authentication and authorisation

| # | Gap | Decision |
| --- | --- | --- |
| C1 | One login for everyone or three? | **One `users` table, one login.** Use an `is_platform_admin` flag plus the `operator_members` join table rather than a single mutually exclusive role column—so any user can book as a customer and also manage an operator organisation. Portals are route areas guarded by membership/admin checks. |
| C2 | Token storage in browser. | Access JWT (15 min) kept in memory; refresh token in `HttpOnly; Secure; SameSite=Lax` cookie, rotated on use with reuse detection (revokes entire token family if a rotated token is replayed), stored hashed server-side. |
| C3 | Operator A reads or edits operator B's data (IDOR). | Every operator query is scoped by `operator_id` derived from the authenticated session's membership context, never from the request body. Automated cross-tenant tests are mandatory. |
| C4 | Self-registration as ADMIN. | Public signup creates standard customer accounts only. Operator access is granted via operator onboarding. Platform `ADMIN` is granted only via CLI seed command. |
| C5 | Brute force and enumeration. | Rate limit login and signup by IP + normalized identifier, generic error messages with constant-time dummy hash verification, `argon2id` hashing, progressive lockout backoff. |

## D. Data integrity and scaling

| # | Gap | Decision |
| --- | --- | --- |
| D1 | Money as floats. | Integer minor units (poisha) in `BIGINT`, currency column fixed to `BDT`. |
| D2 | Time zones. | Store UTC `timestamptz`; trip dates are `date`. Anchor all business cutoffs (expiry, departure booking close) explicitly to `Asia/Dhaka` (`UTC+6`) in a centralized time utility. |
| D3 | Double submit creates two bookings. | `Idempotency-Key` header required on booking creation and payment submission, scoped to `(user_id, endpoint, key)` with a 24-hour TTL. |
| D4 | Status as free text. | PostgreSQL enums + one centralized state-machine module; illegal transitions raise errors and valid transitions write to `audit_logs` in the same DB transaction. |
| D5 | Future flight/hotel portals will clash with tour tables. | Operator org and members are generic. Product tables are tour-specific (`tour_packages`, `tour_departures`). Bookings reference `departure_id` now; v2 adds a generic `booking_items` layer. See 02. |
| D6 | No audit trail. | Append-only `audit_logs` capturing actor, role, entity, action, old/new state, and IP address for admin and operator state changes. |
| D7 | Schema drift across agents. | Alembic migrations only. Agents never edit the DB by hand; CI enforces zero autogenerate drift. |
| D8 | Search and filter slow later. | Composite indexes on `(status, start_date)` and `(destination, status)`, trigram search later. Cursor-based pagination (default 20, max 100) on every list endpoint. |

## E. Operations

| # | Gap | Decision |
| --- | --- | --- |
| E1 | Image uploads. | S3-compatible storage (Cloudflare R2 or Supabase Storage) via presigned upload URLs. Magic-byte MIME type and size validation (max 5MB). Public package photos vs private NID docs in separate buckets. |
| E2 | Background work (expiry, notifications). | v1: authenticated internal endpoint (`POST /internal/cron/sweep`) triggered every 1–2 minutes by an external scheduler (GitHub Actions / Cloudflare Cron / `pg_cron`) to avoid multi-worker duplicates and serverless cold-start misses. v2: dedicated queue worker. |
| E3 | Free-tier cold starts and DB limits. | Use Neon pooled connection string (`-pooler`) with `pool_pre_ping=True`; `/health` endpoint; document cold-start behaviour. |
| E4 | Secrets leak. | `.env` only, `.env.example` committed, never commit real secrets. |
| E5 | Bangladesh data protection and consent. | Terms and privacy consent checkbox at signup; store `consented_at` and `policy_version`. |

## Resolved Product Decisions (Formerly OPEN)

1. **Commission vs subscription (A1):** Record-only in v1 (`commission_bps = 0` stored, GMV logged per confirmed booking); monetize via commission or subscription in v2.
2. **Advance payment verification (A1):** Operator verifies by default (funds go directly to operator's bKash/Nagad); Admin can override or resolve disputes.
3. **User-initiated cancellations (A8):** Allowed before the departure cutoff. Auto-cancels if `PENDING_PAYMENT`; submits cancellation request for operator/admin approval + manual refund logging if `CONFIRMED`.
4. **Language (E5):** English UI with i18n-ready string keys; full UTF-8 Bangla support for package titles, itineraries, notes, and WhatsApp message templates from day one.