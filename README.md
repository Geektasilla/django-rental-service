# Django Rental Service — housing rental backend

Diploma project.

![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Django](https://img.shields.io/badge/django-6-green.svg)
![DRF](https://img.shields.io/badge/DRF-REST%20API-red.svg)

Back-end application (REST API) for renting residential property on the German market: daily and
long-term rentals, listings with a normalized German address, search and filtering, user roles,
bookings, reviews, AI content moderation, GDPR anonymization, async tasks. Payment is implemented
as a stub (`pay()` moves a booking to `PAID` without integrating a real payment gateway) —
payment-provider integration is out of scope for this project.

**Stack:** Django 6 · Django REST Framework · JWT (SimpleJWT) · MySQL (prod) / SQLite (dev) ·
Redis · Celery + Celery Beat · Docker.

---

## 1. Architecture

```
django_rental_service/
├── config/                 # project settings, root urls.py, Celery app, WSGI/ASGI
├── users/                   # User, roles (owner/agent/tenant/support/moderator), JWT, GDPR
├── listings/                # listings, German address (PostalCode→Address→PropertyLocation),
│                             #  categories/amenities, AI moderation of text and photos
├── bookings/                # bookings, status machine, date overlap, price freeze
├── reviews/                 # reviews tied to completed bookings
├── notifications/           # in-app notifications
├── support/                 # helpdesk tickets and messages
├── analytics/                # views/search history, popular searches, retention cleanup
├── common/                  # base models, mixins, shared services, health check
├── locale/                  # translations (en default, de)
├── docker-compose.yml / Dockerfile
└── env_example
```

Every app follows the same layout: `models/` (a package, one file per entity, not a flat
`models.py`), `serializers.py`, `views.py`, `permissions.py`, `services/` (business logic kept out
of the views), `tests/`, `migrations/` (including hand-written `RunSQL`/`RunPython` triggers — see
section 7).

**Request flow:** `HTTP → permissions → serializer (validation) → view/service (business rules,
sometimes @transaction.atomic + select_for_update) → ORM → response`.

Per-action permissions (create/update/delete/…) aren't resolved with an if/elif chain but through
the declarative `ActionPermissionsMixin` (`common/mixins.py`) — a `permission_classes_by_action`
dict on every ViewSet that needs it (`PropertyViewSet`, `BookingViewSet`, `TicketViewSet`).

---

## 2. Quick start (local, SQLite)

For local development the default database is SQLite — no MySQL needed.

```bash
# 1. Dependencies (managed via uv)
uv sync

# 2. Environment file
cp env_example .env        # USE_REMOTE=False → SQLite

# 3. Migrations and superuser
uv run python manage.py migrate
uv run python manage.py createsuperuser     # optional, for /admin/

# 4. Demo data (optional)
uv run python manage.py seed_data           # only works with DEBUG=True

# 5. Run
uv run python manage.py runserver
```

The API comes up at `http://127.0.0.1:8000/`.

---

## 3. Running via Docker (MySQL)

```bash
cp env_example .env
docker compose up --build
```

Four services come up: `redis` (with a health check), `web` (Gunicorn), `worker` (Celery), and
`beat` (Celery Beat — runs `cleanup-analytics-daily` every day at 03:00). Before starting, `web`
runs migrations and collects static files itself (via the container's `command:`); demo data is
not seeded automatically — see section 10.

A superuser is not created automatically — to access `/admin/`:

```bash
docker compose exec web python manage.py createsuperuser
```

---

## 4. Environment variables (`.env`)

The full annotated template is `env_example`. Key groups:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key, unique per environment |
| `DEBUG` | debug mode (must be `False` in production) |
| `ALLOWED_HOSTS` | comma-separated allowed hosts |
| `USE_REMOTE` | `True` → MySQL (`DB_*`), `False` → SQLite (dev) |
| `DB_NAME/USER/PASSWORD/HOST/PORT` | MySQL connection parameters |
| `REDIS_URL` | Redis for caching and DRF throttling |
| `AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY/REGION_NAME` | AWS Rekognition — photo moderation |
| `OPENAI_API_KEY` | OpenAI Moderation API — text moderation |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP for password-reset / email-verification messages |
| `FRONTEND_URL`, `CORS_EXTRA_ORIGINS` | links in emails, extra CORS origins |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis-backed Celery broker/result store |
| `ANALYTICS_RETENTION_DAYS` | how long SearchHistory/PropertyView rows are kept before `cleanup_analytics` (default 90) |

*AI moderation (OpenAI/AWS) and email are optional in development — the app degrades gracefully
(logs a warning and skips the check) when the keys are left unset.*

---

## 5. API — endpoints

Base prefix: `/api/v1/`. Authentication — JWT: `Authorization: Bearer <access>` header.
Interactive docs: `http://localhost:8000/api/schema/swagger-ui/`.

### Authentication (`/api/v1/auth/`)

| Method | Path | Access | Description |
|---|---|---|---|
| POST | `register/` | anyone (throttle 10/hour) | Registration |
| POST | `login/` | anyone | Login → `access`/`refresh` |
| POST | `login/refresh/` | anyone | Refresh the access token |
| POST | `logout/` | authenticated | Blacklists the refresh token |
| POST | `password-reset/request/` | anyone (throttle 5/hour) | Request a password reset |
| POST | `password-reset/confirm/` | anyone (throttle 5/hour) | Confirm the reset |
| POST | `email-verification/confirm/` | anyone (throttle 5/hour) | Confirm email |

### User profile (`/api/v1/users/`)

| Method | Path | Access | Description |
|---|---|---|---|
| GET/PUT/PATCH | `me/` | authenticated | Own User profile |
| POST | `me/password/` | authenticated | Change password (revokes all sessions) |
| POST | `me/email-verification/request/` | authenticated | Request a verification email |
| POST | `me/delete-account/` | authenticated | GDPR account anonymization |
| GET/POST/PATCH | `me/owner-profile/` | authenticated (`is_owner`) | Owner profile |
| GET/POST/PATCH | `me/agent-profile/` | authenticated (`is_agent`) | Agent profile |
| GET/POST/PATCH | `me/tenant-profile/` | authenticated | Tenant profile |
| POST | `<id>/owner-profile/verify/` | moderator | Verify owner documents |
| POST | `<id>/agent-profile/certify/` | moderator | Certify an agent |

### Listings (`/api/v1/listings/`)

| Method | Path | Access | Description |
|---|---|---|---|
| GET | `categories/`, `amenities/` | anyone | Reference data for the create-listing form |
| GET | `` | anyone (guests see only `approved` + active) | Catalog with filters |
| POST | `` | owner/agent | Create a listing |
| GET | `<id>/` | anyone | Listing detail (+ logs a view) |
| PATCH | `<id>/` | property owner | Edit |
| DELETE | `<id>/` | property owner | Delete (409 if bookings exist) |
| POST/DELETE | `<id>/images/[<image_id>/]` | property owner | Upload/delete a photo (limit 10) |
| POST | `<id>/moderate/` | moderator | Manual approve/reject decision |
| GET | `<id>/reviews/` | anyone | Reviews for the listing |

*An empty path means the resource's root address — `GET`/`POST /api/v1/listings/` with no tail
(the standard DRF router's list/create endpoints).*

**Catalog query parameters:** category, rent type, listing type, city, room-count range, a single
price range that works for both daily and monthly rent types.

### Bookings (`/api/v1/bookings/`)

| Method | Path | Access | Description |
|---|---|---|---|
| POST | `` | tenant | Create a booking (`PENDING`) |
| GET | `` / `<id>/` | authenticated | Own bookings (tenant/owner), everything for staff |
| POST | `<id>/confirm/` | property owner/agent | `PENDING → BOOKED`, auto-cancels overlapping requests |
| POST | `<id>/pay/` | property owner/agent | `BOOKED → PAID` (payment stub) |
| POST | `<id>/cancel/` | booking participant | Cancel (BOOKED/PAID — no later than 21 days out) |
| POST | `<id>/review/` | booking's tenant | Leave a review (PAID only, 90-day window) |

*The empty path for `POST` is the same case as in the listings table — the resource root
`POST /api/v1/bookings/` (create). There's no separate row for the `GET /api/v1/bookings/` list
endpoint under an empty path — it's merged with the `<id>/` row above.*

### Notifications and support

| Method | Path | Access | Description |
|---|---|---|---|
| GET / `<id>/` / PATCH | `/api/v1/notifications/` | authenticated | Own notifications, mark as read |
| POST | `/api/v1/support/` | authenticated | Open a ticket (auto-assigned to an agent) |
| GET / `<id>/` | `/api/v1/support/` | opener/assigned/staff | List/detail of a ticket |
| PATCH | `/api/v1/support/<id>/` | assigned agent | Change ticket status |
| GET/POST | `/api/v1/support/<id>/messages/` | anyone who can see the ticket | Ticket conversation |

### Analytics

| Method | Path | Access | Description |
|---|---|---|---|
| GET | `/api/v1/analytics/popular-searches/` | anyone | Popular search queries |

---

## 6. Roles and business rules

**Roles** are not an exclusive enum but additive profiles: one account can be
`OwnerProfile`/`AgentProfile`/`TenantProfile` at the same time. The `is_owner`/`is_agent` flags on
`User` are self-set by the user during registration/profile updates, but by themselves grant no
access — an active (`status=active`) profile of the matching role is also required. `is_support`/
`is_moderator` can't be self-set by the user — admin only. `OwnerProfile.is_verified` and
`AgentProfile.is_certified` follow a "user applies, moderator confirms" pattern — never settable by
the user themself.

**Booking statuses:** `PENDING → BOOKED → PAID`, or `CANCELLED` at any point before PAID.
- Date overlap is only forbidden between `BOOKED`/`PAID` bookings on the same property (`PENDING`
  doesn't block dates) — checked both in `Booking.clean()` and by a dedicated DB trigger (see
  section 7), since `bulk_create`/`.update()` (used by `confirm()`'s auto-cancel) bypass `clean()`.
- `price_frozen` locks in the property's price at booking-creation time — a later price change by
  the owner never affects existing bookings.
- A confirmed (`BOOKED`/`PAID`) booking can only be cancelled no later than 21 days before check-in.
- A review can only be left for a `PAID` booking, no later than 90 days after `end_date`, and only
  once per booking.

---

## 7. Two-layer validation: CheckConstraint + DB triggers

Every model that can be bulk-modified in a way that bypasses `clean()` (`bulk_create`/
`bulk_update`/`.update()`), and where that actually happens in the codebase, is protected not only
by Python validation but at the database schema level too:

- **`CheckConstraint`** (single-row rules): review rating range (1–5), booking date order
  (`end_date > start_date`), valid status/gender values.
- **DB triggers** (cross-row rules that `CheckConstraint` can't express, implemented separately
  for SQLite and MySQL via `RunSQL`/`RunPython`):
  - booking date overlap (`bookings`);
  - the 90-day review window (`reviews`);
  - agent certification when creating a `listed_as='agent'` listing, plus a mirror trigger that
    blocks decertifying an agent while they still have active listings (`users`/`listings`);
  - the per-listing photo count limit (`listings`).

  Threshold values (`90`, `10`, `21`) are hardcoded in the SQL itself — a trigger can't read Django
  settings, so changing the corresponding constants in `settings.py` also requires updating the
  migration (canary tests catch drift here).

---

## 8. Tests

65+ tests, laid out as `<app>/tests/test_*.py` — organized by scenario/business rule (e.g.
`test_booking_overlap_trigger.py`, `test_review_window_trigger.py`,
`test_permission_boundaries.py`), not by technical code layer.

```bash
python manage.py test
```

CI: `.github/workflows/tests.yml` — runs the full test suite on GitHub Actions on every push/PR to
`main`/`develop` (SQLite + a Redis service, no real secrets).

---

## 9. Security

- **JWT**: refresh-token rotation with blacklisting; logout and password change/reset explicitly
  revoke all of the user's active sessions.
- **Throttling**: dedicated tight limits on registration, password reset, and email verification —
  protects against brute-force/spam.
- **AI content moderation**: listing text via the OpenAI Moderation API, photos via AWS
  Rekognition. Automation can only **reject** a listing — approval is always manual, by a
  moderator. If the keys are missing or the call errors out, moderation fails open rather than
  blocking content, and logs the error to `ModerationLog`.
- **GDPR**: self-service account deletion is not a hard delete but anonymization of personal data
  (booking/ticket history is retained per legal requirements), plus scheduled cleanup of analytics
  data older than `ANALYTICS_RETENTION_DAYS`.
- **Production settings** (`DEBUG=False`): HTTPS redirect, HSTS, secure cookies,
  `X-Content-Type-Options: nosniff`.
- **Two-layer validation** of business rules — Python (`clean()`) + database
  (`CheckConstraint`/triggers, see section 7) — data stays protected even if the serializer/service
  layer is bypassed.

---

## 10. Seeding the database with demo data

The command only works with `DEBUG=True` (otherwise it raises an explicit error, to avoid
accidentally seeding production) and is **always run manually** — there is no automatic seeding on
container startup.

Without Docker:
```bash
python manage.py seed_data
```

Inside an already-running Docker container, without touching `DEBUG` in `.env` or restarting the
service:
```bash
docker compose exec web env DEBUG=True python manage.py seed_data
```
`env DEBUG=True` overrides the variable only for this one call — the already-running `gunicorn`
process keeps responding with `DEBUG=False` (production security settings stay on) exactly as
before.

Generates a realistic set of data via Faker (`de_DE`): categories/amenities/German addresses, ~150
users with profiles for every role, ~100 listings with photos, bookings (including completed ones),
reviews, search/view history, support tickets. The command is idempotent — re-running it tops up
existing data instead of recreating everything from scratch.

Scheduled analytics cleanup:

```bash
python manage.py cleanup_analytics
```
