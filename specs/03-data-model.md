Set up this app on Neon.
1. `npm i -g neon@latest`. If that fails, use `npx neon@latest` in place of `neon`.
   If a neon command opens a browser sign-in, tell me to finish it there. If that times out or fails, ask me to run `neon login`, then retry.
2. In the project root:
   neon init -y --org-id org-blue-mountain-42782632 --project-id muddy-block-52137380 --branch production --services postgres
3. `neon deploy`. It provisions the services in neon.ts and pulls their env vars into `.env.local` (or `.env` if it exists).
4. Wire each service into the app's code using those env vars. Consult the installed Neon agent skills for best practices, e.g., what database driver to use given the app architecture and hosting runtime.
5. Prove it works: `npm run build` must pass, then start the app, each wired service must be tested to prove it works end to end.
6. Report what changed, the command output that proves step 5, and anything that failed.

# 03 - Data Model (PostgreSQL)

Conventions: `id uuid pk`, `created_at/updated_at timestamptz`, money `bigint` poisha, enums as text with CHECK constraints, no hard deletes. Implement via SQLAlchemy models + Alembic; the SQL below is the contract.

```sql
-- IDENTITY
CREATE TABLE users (
  id uuid PRIMARY KEY,
  full_name text NOT NULL,
  email citext UNIQUE NOT NULL,
  phone text UNIQUE NOT NULL,                  -- +8801XXXXXXXXX
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('CUSTOMER','OPERATOR','ADMIN')) DEFAULT 'CUSTOMER',
  status text NOT NULL CHECK (status IN ('ACTIVE','SUSPENDED')) DEFAULT 'ACTIVE',
  phone_verified_at timestamptz,
  consented_at timestamptz NOT NULL,
  failed_logins int NOT NULL DEFAULT 0,
  locked_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id),
  token_hash text NOT NULL UNIQUE,
  family_id uuid NOT NULL,                      -- rotation chain; reuse => revoke family
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- OPERATORS (domain neutral)
CREATE TABLE operators (
  id uuid PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('TOUR')) DEFAULT 'TOUR',   -- later: HOTEL, AIRLINE
  type text NOT NULL CHECK (type IN ('INDIVIDUAL','GROUP')),
  display_name text NOT NULL,
  contact_phone text NOT NULL UNIQUE,
  facebook_url text,
  payout_methods jsonb NOT NULL DEFAULT '[]',   -- e.g. [{"provider":"BKASH","number":"01..."}]
  commission_bps int NOT NULL DEFAULT 0 CHECK (commission_bps BETWEEN 0 AND 10000),
  verification_status text NOT NULL CHECK (verification_status IN ('DRAFT','PENDING','APPROVED','REJECTED','SUSPENDED')) DEFAULT 'DRAFT',
  verification_note text,
  verified_by uuid REFERENCES users(id),
  verified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE operator_members (
  operator_id uuid NOT NULL REFERENCES operators(id),
  user_id uuid NOT NULL REFERENCES users(id),
  member_role text NOT NULL CHECK (member_role IN ('OWNER','STAFF')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (operator_id, user_id)
);
CREATE UNIQUE INDEX one_owner_per_operator ON operator_members(operator_id) WHERE member_role='OWNER';

CREATE TABLE verification_documents (
  id uuid PRIMARY KEY,
  operator_id uuid NOT NULL REFERENCES operators(id),
  person_name text NOT NULL,
  doc_type text NOT NULL CHECK (doc_type IN ('NID_FRONT','NID_BACK','SELFIE','AUTHORIZATION_NOTE')),
  nid_encrypted bytea,                          -- app-level encryption
  nid_hash text,                                -- HMAC for duplicate detection
  nid_last4 text,
  storage_key text NOT NULL,                    -- private bucket
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_nid_hash ON verification_documents(nid_hash) WHERE nid_hash IS NOT NULL AND doc_type='NID_FRONT';

-- CATALOG
CREATE TABLE tour_packages (
  id uuid PRIMARY KEY,
  operator_id uuid NOT NULL REFERENCES operators(id),
  title text NOT NULL,
  slug text UNIQUE NOT NULL,
  destination text NOT NULL,                    -- normalised label, e.g. "Sajek Valley"
  summary text NOT NULL,
  description text NOT NULL,
  itinerary jsonb NOT NULL DEFAULT '[]',
  inclusions text[] NOT NULL DEFAULT '{}',
  exclusions text[] NOT NULL DEFAULT '{}',
  duration_days int NOT NULL CHECK (duration_days >= 1),
  base_price bigint NOT NULL CHECK (base_price >= 0),
  advance_percent int NOT NULL DEFAULT 30 CHECK (advance_percent BETWEEN 0 AND 100),
  cancellation_policy text NOT NULL,
  status text NOT NULL CHECK (status IN ('DRAFT','PUBLISHED','SUSPENDED','ARCHIVED')) DEFAULT 'DRAFT',
  status_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_pkg_status_dest ON tour_packages(status, destination);
CREATE INDEX ix_pkg_operator ON tour_packages(operator_id);

CREATE TABLE tour_package_images (
  id uuid PRIMARY KEY,
  package_id uuid NOT NULL REFERENCES tour_packages(id),
  storage_key text NOT NULL,
  position int NOT NULL DEFAULT 0
);

CREATE TABLE departures (
  id uuid PRIMARY KEY,
  package_id uuid NOT NULL REFERENCES tour_packages(id),
  start_date date NOT NULL,
  end_date date NOT NULL,
  price bigint NOT NULL CHECK (price >= 0),     -- per seat
  capacity int NOT NULL CHECK (capacity > 0),
  seats_booked int NOT NULL DEFAULT 0,
  booking_cutoff timestamptz,
  status text NOT NULL CHECK (status IN ('OPEN','CLOSED','CANCELLED')) DEFAULT 'OPEN',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (seats_booked >= 0 AND seats_booked <= capacity),
  CHECK (end_date >= start_date)
);
CREATE INDEX ix_dep_date ON departures(start_date, status);
CREATE INDEX ix_dep_package ON departures(package_id);

CREATE TABLE offers (
  id uuid PRIMARY KEY,
  package_id uuid NOT NULL REFERENCES tour_packages(id),
  title text NOT NULL,
  discount_type text NOT NULL CHECK (discount_type IN ('PERCENT','FLAT')),
  discount_value bigint NOT NULL CHECK (discount_value > 0),  -- percent (1-100) or poisha
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_by uuid NOT NULL REFERENCES users(id),
  CHECK (ends_at > starts_at)
);

-- BOOKINGS
CREATE TABLE bookings (
  id uuid PRIMARY KEY,
  reference text UNIQUE NOT NULL,               -- human code, e.g. TB-8K2M9Q
  departure_id uuid NOT NULL REFERENCES departures(id),
  user_id uuid REFERENCES users(id),            -- NULL for manual (facebook/phone) bookings
  contact_name text NOT NULL,
  contact_phone text NOT NULL,
  source text NOT NULL CHECK (source IN ('WEB','FACEBOOK','PHONE','WALK_IN')) DEFAULT 'WEB',
  seats int NOT NULL CHECK (seats > 0),
  unit_price bigint NOT NULL,                   -- snapshot, after offer
  offer_id uuid REFERENCES offers(id),
  total_amount bigint NOT NULL,
  advance_required bigint NOT NULL,
  status text NOT NULL CHECK (status IN (
    'PENDING_PAYMENT','AWAITING_VERIFICATION','CONFIRMED','COMPLETED','EXPIRED',
    'REJECTED','CANCELLATION_REQUESTED','CANCELLED','CANCELLED_UNAVAILABLE')) DEFAULT 'PENDING_PAYMENT',
  expires_at timestamptz,
  needs_attention boolean NOT NULL DEFAULT false,
  created_by uuid REFERENCES users(id),         -- who created (admin/operator for manual)
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (total_amount = unit_price * seats)
);
CREATE INDEX ix_booking_user ON bookings(user_id, created_at DESC);
CREATE INDEX ix_booking_departure ON bookings(departure_id, status);
CREATE INDEX ix_booking_expiry ON bookings(expires_at) WHERE status IN ('PENDING_PAYMENT');

CREATE TABLE booking_travellers (
  id uuid PRIMARY KEY,
  booking_id uuid NOT NULL REFERENCES bookings(id),
  full_name text NOT NULL,
  age int,
  gender text
);

CREATE TABLE booking_events (                    -- status timeline
  id uuid PRIMARY KEY,
  booking_id uuid NOT NULL REFERENCES bookings(id),
  from_status text, to_status text NOT NULL,
  actor_id uuid REFERENCES users(id),
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE payments (
  id uuid PRIMARY KEY,
  booking_id uuid NOT NULL REFERENCES bookings(id),
  provider text NOT NULL CHECK (provider IN ('BKASH','NAGAD','ROCKET','CASH','GATEWAY')),
  amount bigint NOT NULL CHECK (amount > 0),
  sender_number text,
  provider_txn_id text,
  status text NOT NULL CHECK (status IN ('SUBMITTED','VERIFIED','REJECTED','REFUNDED')) DEFAULT 'SUBMITTED',
  verified_by uuid REFERENCES users(id),
  verified_at timestamptz,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_txn ON payments(provider, provider_txn_id) WHERE provider_txn_id IS NOT NULL AND status <> 'REJECTED';

-- PLATFORM
CREATE TABLE notifications (
  id uuid PRIMARY KEY,
  user_id uuid REFERENCES users(id),
  booking_id uuid REFERENCES bookings(id),
  channel text NOT NULL CHECK (channel IN ('IN_APP','MANUAL_MESSAGE')) DEFAULT 'IN_APP',
  title text NOT NULL, body text NOT NULL,
  read_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
  id uuid PRIMARY KEY,
  actor_id uuid REFERENCES users(id),
  action text NOT NULL,                          -- e.g. OPERATOR_APPROVED, NID_VIEWED
  entity_type text NOT NULL, entity_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}',
  ip inet,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE idempotency_keys (
  user_id uuid NOT NULL REFERENCES users(id),
  key text NOT NULL,
  request_hash text NOT NULL,
  response jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, key)
);
```

## Invariants (must be enforced and tested)
1. `departures.seats_booked` equals the sum of `seats` of bookings in active statuses (`PENDING_PAYMENT`, `AWAITING_VERIFICATION`, `CONFIRMED`, `CANCELLATION_REQUESTED`, `COMPLETED`). Provide a reconciliation CLI that reports drift.
2. A package is visible publicly only if package `PUBLISHED` and operator `APPROVED`.
3. Booking `total_amount` never changes after creation.
4. A verified payment total never exceeds `total_amount`.
5. Operator data is reachable only through `operator_members` of the current user.
