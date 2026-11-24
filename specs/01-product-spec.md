# 01 - Product Spec (v1)

## Roles
- **Customer** (public signup), **Operator** (tour guide or group member, needs admin approval to publish), **Admin** (seeded).
- Guest browsing is allowed (view tours and departures). Booking requires login.

## Epics, user stories and acceptance criteria

### A. Accounts
- **US-A1** As a visitor I register with name, phone, email, password and consent. *AC:* phone matches `+8801[3-9]\d{8}`; email and phone unique; role is CUSTOMER; password >= 8 chars; consent timestamp stored.
- **US-A2** As a user I log in and stay logged in. *AC:* access token 15 min, refresh cookie rotates; logout revokes refresh token; 5 failed logins in 10 min triggers temporary lockout.
- **US-A3** As an operator I onboard: create operator profile (INDIVIDUAL or GROUP), upload NID front/back and a selfie or authorisation note, add Facebook page/group URL. *AC:* status `PENDING`; I can draft packages but cannot publish; NID never returned by non-admin APIs.
- **US-A4** As an operator owner I invite staff by phone/email. *AC:* STAFF can manage departures and bookings, not payout details or members.

### B. Discovery (customer)
- **US-B1** Browse and filter published packages by destination, date range, price range, duration, with pagination and sort. *AC:* only `PUBLISHED` packages of `APPROVED` operators appear.
- **US-B2** View a package: description, itinerary, inclusions, photos, operator badge (verified), cancellation policy, upcoming departures with remaining seats and price (offer price shown struck-through).
- **US-B3** Date search: "available on 26 Dec" lists departures on that date with seats left >= 1.
- **US-B4** See current offers on a dedicated page and on cards.

### C. Booking (customer)
- **US-C1** Book a departure for N seats with traveller details. *AC:* seats reserved atomically; if seats insufficient -> 409 `SEATS_UNAVAILABLE`; booking `PENDING_PAYMENT`, expires in 30 min; price snapshot stored; `Idempotency-Key` honoured.
- **US-C2** Pay advance (dummy): choose bKash/Nagad/Rocket/Cash-at-office, enter sender number and transaction id. *AC:* payment `SUBMITTED`; booking moves to `AWAITING_VERIFICATION`; seats stay held.
- **US-C3** See my bookings and their status timeline. *AC:* only my bookings.
- **US-C4** Request cancellation. *AC:* booking `CANCELLATION_REQUESTED`; operator/admin decides.
- **US-C5** See in-app notifications (e.g. booking confirmed, package unavailable).

### D. Operator portal
- **US-D1** CRUD tour packages (draft -> submit to publish). *AC:* publish allowed only if operator APPROVED; edits to published package fields that affect price are applied only to future departures.
- **US-D2** Manage departures: date, price, capacity, cut-off. *AC:* capacity cannot drop below seats already booked; cancelling a departure with active bookings uses the bulk-cancel flow.
- **US-D3** See bookings for my packages, filter by status/departure. *AC:* only my operator's data (cross-tenant test required).
- **US-D4** Verify or reject a submitted payment; confirm or reject a booking. *AC:* verified payment + advance >= required advance amount -> booking `CONFIRMED`; rejection with reason notifies customer.
- **US-D5** Create manual booking (source phone/facebook/walk-in) with contact name and phone, no account needed.
- **US-D6** Dashboard: upcoming departures, seats sold, pending verifications.

### E. Admin panel
- **US-E1** Review operator applications: view documents (signed URLs, logged), approve, reject with reason, suspend.
- **US-E2** View all bookings with filters (status, operator, date, source); export CSV.
- **US-E3** Moderate packages: unpublish/suspend with reason (operator is notified; open bookings flagged).
- **US-E4** Create manual booking on behalf of a customer (Facebook edge case) and flag **needs attention**.
- **US-E5** "Notify unavailable": for a booking whose package/departure is unavailable, set `CANCELLED_UNAVAILABLE`, release seats, create a notification, show copyable message text for Facebook/phone follow-up.
- **US-E6** Manage offers (create, edit, deactivate) and view audit log.
- **US-E7** Dashboard: counts by status, revenue booked (sum of verified advances), pending operator applications.

## Booking state machine
```
PENDING_PAYMENT --submit payment--> AWAITING_VERIFICATION --verify--> CONFIRMED --trip done--> COMPLETED
PENDING_PAYMENT --timeout--> EXPIRED
PENDING_PAYMENT/AWAITING_VERIFICATION --reject--> REJECTED
CONFIRMED --cancel request--> CANCELLATION_REQUESTED --approve--> CANCELLED / --deny--> CONFIRMED
any active state --unavailable--> CANCELLED_UNAVAILABLE
```
Seats are released on EXPIRED, REJECTED, CANCELLED, CANCELLED_UNAVAILABLE. A manual booking may start at `CONFIRMED` if the creator records an advance.

## Non-functional requirements
- p95 list endpoint < 500 ms at 10k packages; paginated.
- 100% of write endpoints covered by authorisation tests.
- Accessible, mobile-first UI (most users are on phones); Lighthouse mobile >= 80.
- English UI with strings in a translation file for later Bangla.
