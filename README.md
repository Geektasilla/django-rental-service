# Django Rental Service

## Project description

Django Rental Service is a REST API platform for renting residential property on the German
market: daily and long-term rentals, listings with a normalized German address, search and
filtering, user roles, bookings, reviews, AI content moderation, GDPR anonymization, async tasks.
Payment is implemented as a stub (`pay()` moves a booking to `PAID` without integrating a real
payment gateway).

All user-facing text (error messages, field labels, email content, etc.) supports two languages —
English (default) and German — switched through Django's standard internationalization mechanism
(`gettext_lazy`, translation catalogs under `locale/`).

## Tech stack

* Python 3.12, Django 6, Django REST Framework
* JWT authentication (SimpleJWT)
* MySQL (production) / SQLite (dev)
* Redis — cache, DRF throttling, Celery broker and result backend
* Celery + Celery Beat — async tasks and periodic jobs
* OpenAI Moderation API + AWS Rekognition — AI moderation of text and photos
* Docker / Docker Compose — containerization
* nginx + Let's Encrypt (certbot) — TLS termination in production
* uv — dependency management

## Project structure

```
django_rental_service/
├── config/          # project settings, root urls.py, Celery app, WSGI/ASGI
├── users/            # User, roles (owner/agent/tenant/support/moderator), JWT, GDPR
├── listings/          # listings, German address, categories/amenities, AI moderation
├── bookings/           # bookings, status machine, date overlap, price freeze
├── reviews/             # reviews tied to completed bookings
├── notifications/        # in-app notifications
├── support/               # support tickets and conversations
├── analytics/              # search/view history, popular searches
├── common/                  # base models, mixins, shared services, health check
├── locale/                    # translations (en default, de)
├── templates/                   # shared Django templates
├── media/                         # uploaded files (listing photos, documents)
├── tools/                           # helper scripts, documentation, QA checklists
├── Dockerfile, docker-compose.yml     # containerization
├── pyproject.toml, uv.lock              # dependencies (uv)
└── env_example                            # environment variable template
```

Every app follows the same layout: `models/` (a package, one file per entity), `serializers.py`,
`views.py`, `permissions.py`, `services/` (business logic), `tests/`, `migrations/` (including
hand-written `RunSQL`/`RunPython` triggers for rules that bypass `clean()` during bulk ORM
operations).

## Local development (SQLite)

```bash
git clone <repository URL>
cd django_rental_service

uv sync
cp env_example .env        # USE_REMOTE=False → SQLite, no MySQL needed
                            # ALLOWED_HOSTS=127.0.0.1,localhost — the default, no need to change it

uv run python manage.py migrate
uv run python manage.py createsuperuser     # optional, for /admin/
uv run python manage.py seed_data           # optional, only works with DEBUG=True

uv run python manage.py runserver
```

The app comes up at `http://127.0.0.1:8000/` (local only — in production port 8000 is closed
externally, see the "HTTPS and certificate" section).

## Running via Docker (MySQL)

```bash
cp env_example .env        # USE_REMOTE=True + fill in DB_*
docker compose up --build
```

Four services come up: `redis`, `web` (Gunicorn), `worker`, and `beat` (Celery). Before starting,
`web` applies migrations and collects static files itself. Demo data is not seeded automatically.

```bash
docker compose exec web python manage.py createsuperuser
```

## Deploying to AWS

The server is an EC2 instance (Ubuntu); the app runs via Docker Compose, updated via `git pull`
plus a container rebuild:

```bash
ssh -i ~/.ssh/<key>.pem ubuntu@<server address>

cd /home/ubuntu/django-rental-service
git checkout develop && git pull origin develop

docker compose down
docker compose up -d --build
```

Updating a single service without taking the others down (e.g. after a Django-only code change):

```bash
docker compose up --build web
```

Useful commands on the server:

```bash
docker ps -a                                          # container status
docker logs <container_id>                             # container logs
docker compose exec web python manage.py createsuperuser
docker compose exec web env DEBUG=True python manage.py seed_data   # seed demo data
docker compose exec web python manage.py flush --no-input           # wipe the database
```

## API documentation (Swagger)

Interactive documentation for every endpoint is auto-generated via `drf-spectacular` and served at
`/api/schema/swagger-ui/`:

* locally — `http://127.0.0.1:8000/api/schema/swagger-ui/`;
* in production — [https://63-180-97-86.sslip.io/api/schema/swagger-ui/](https://63-180-97-86.sslip.io/api/schema/swagger-ui/).

You can also make requests directly from the browser there — just authenticate with a JWT via the
Authorize button.

The raw OpenAPI schema is at `/api/schema/`.

## Email

Email delivery (password reset, address confirmation, notifying an owner about a new booking
request) goes through Django's standard SMTP backend, configured via `EMAIL_HOST`, `EMAIL_PORT`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`.

* **In development**, the [Mailtrap](https://mailtrap.io/) sandbox is used — emails never reach
  real recipients, they're captured in a test inbox for inspection.
* Missing email credentials don't break the app — a send failure is logged but doesn't block the
  main request (e.g. creating a booking isn't rolled back if the email fails to send).
* Links inside emails (password reset, email confirmation) are built from `FRONTEND_URL`.

## HTTPS and certificate

In production, **nginx** sits in front of Gunicorn and terminates TLS:

* the certificate is issued by Let's Encrypt via `certbot`, with auto-renewal configured;
* `SECURE_PROXY_SSL_HEADER` in `settings.py` tells Django to trust nginx's `X-Forwarded-Proto`
  header — without it the HTTPS redirect loops forever;
* port `8000` (where Gunicorn listens) is closed in the AWS Security Group from the outside — all
  external traffic goes through `80`/`443` only, so there's no way to bypass HTTPS and hit Django
  directly;
* with `DEBUG=False`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, secure cookies, and
  `X-Content-Type-Options: nosniff` are all enabled.

## Environment variables

The full annotated template is `env_example`. Key groups: `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`,
`USE_REMOTE` + `DB_*` (MySQL), `REDIS_URL`, `AWS_*` (photo moderation), `OPENAI_API_KEY` (text
moderation), `EMAIL_*` (SMTP), `FRONTEND_URL`/`CORS_EXTRA_ORIGINS`,
`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`, `ANALYTICS_RETENTION_DAYS`.

AI moderation and email are optional in development — the app degrades gracefully (logs a warning
and skips the check) when the corresponding keys are left unset.

## Testing

```bash
python manage.py test
```

65+ tests, laid out as `<app>/tests/test_*.py` by scenario/business rule. CI (GitHub Actions) runs
the full suite on every push/PR to `main`/`develop`.
