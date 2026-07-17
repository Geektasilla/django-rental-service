# Django Rental Service

## Project Overview
Django Rental Service is a REST API backend built with Django REST Framework (DRF) for a residential property rental platform supporting both short-term (daily) and long-term leasing, tailored to German address formats. It features a normalized (3NF) database schema, JWT-based authentication with role-based access control, AI-assisted content moderation, and asynchronous task processing via Celery.

## Features
*   **JWT Authentication**: Secure login with token rotation and blacklisting; password reset revokes all active sessions.
*   **Role-Based Access Control**: Distinct permissions for owners, agents, tenants, support staff, and moderators.
*   **Property Listings**: Normalized address model (Address / PostalCode / PropertyLocation) built for the German market, with categories, amenities, and image galleries.
*   **Filtering & Search**: Listings can be filtered by category, rent type, listing type, city, room count range, and a unified price range that works across both daily and monthly rent types.
*   **Bookings**: Status-driven booking workflow with automatic date-overlap prevention.
*   **Reviews**: Reviews tied to completed bookings only.
*   **AI Content Moderation**: Text moderation via the OpenAI API and image moderation via AWS Rekognition, with graceful no-op fallback when credentials are absent.
*   **GDPR Compliance**: Self-service account deletion with data anonymization.
*   **Notifications & Support**: In-app notifications and a helpdesk ticketing system.
*   **Analytics**: Property view and search-history tracking, with a popular-searches endpoint and scheduled data retention cleanup.
*   **Internationalization**: English (default) and German, wired into both the Django admin and the DRF Browsable API.
*   **API Documentation**: Interactive OpenAPI/Swagger docs via `drf-spectacular`.
*   **Async Processing**: Celery workers and Celery Beat for background jobs (emails, notifications, scheduled cleanup).

## Tech Stack
*   **Backend**: Python 3.12, Django 6, Django REST Framework
*   **Database**: MySQL (production), SQLite (local development)
*   **Cache / Broker**: Redis, Celery, Celery Beat
*   **Auth**: `djangorestframework-simplejwt`
*   **AI Moderation**: OpenAI API (text), AWS Rekognition via `boto3` (images)
*   **Docs**: `drf-spectacular` (OpenAPI/Swagger)
*   **Static Files**: WhiteNoise
*   **Package Manager**: `uv`
*   **Linting**: `ruff`
*   **Deployment**: Docker, Docker Compose, Gunicorn

## Installation

### Prerequisites
Before you begin, ensure you have the following installed on your system:
*   **Python 3.12+**
*   **uv** (Python package manager)
*   **Docker & Docker Compose** (recommended for local setup)
*   **MySQL** (only required if running without Docker and without SQLite)
*   **Redis** (only required if running without Docker)

### Setup Steps

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-username/django_rental_service.git
    cd django_rental_service
    ```

2.  **Configure Environment Variables**:
    Copy the example file and fill in your own values:
    ```bash
    cp .env.example .env
    ```
    Key variables to review:
    ```
    SECRET_KEY=
    DEBUG=True
    ALLOWED_HOSTS=
    USE_REMOTE=False
    DB_NAME=
    DB_USER=
    DB_PASSWORD=
    DB_HOST=
    DB_PORT=
    REDIS_URL=

    AWS_ACCESS_KEY_ID=
    AWS_SECRET_ACCESS_KEY=
    AWS_REGION_NAME=eu-central-1

    OPENAI_API_KEY=

    CELERY_BROKER_URL=redis://127.0.0.1:6379/0
    CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
    ```
    *AI moderation (OpenAI/AWS) and email settings are optional in development — the app degrades gracefully when these keys are left empty.*

3a. **Run with Docker (recommended)**:
    ```bash
    docker compose up --build
    ```
    This starts `redis`, the `web` app (Gunicorn), a Celery `worker`, and Celery `beat`. On startup, the entrypoint script runs migrations and auto-seeds demo data if `DEBUG=True` and the database is empty.

3b. **Run locally without Docker**:
    ```bash
    uv sync
    python manage.py migrate
    python manage.py runserver
    ```

## Usage

Once running, the API is available at `http://localhost:8000/`.

*   **Swagger / OpenAPI docs**: `http://localhost:8000/api/schema/swagger-ui/`
*   **Django Admin**: `http://localhost:8000/admin/`

### Seeding Demo Data
When running via Docker with `DEBUG=True`, `entrypoint.sh` seeds the database automatically on first startup, but only if the `Property` table is empty — on every later restart it detects existing data and skips seeding, so no manual step is needed for a first run. If you need fresh demo data again (e.g. after testing has changed the state of a non-empty database), wipe the relevant tables yourself first, then run:
```bash
python manage.py seed_data
```
Generates Faker-based demo users, listings, and bookings (development only).

### Running Tests
```bash
python manage.py test
```

## Project Structure
*   `config/`: Project settings, root URL configuration, Celery app, ASGI/WSGI entry points.
*   `users/`: Custom `User` model (email login), owner/agent/tenant profiles, JWT auth, GDPR anonymization.
*   `listings/`: Property listings, normalized German address model, categories, amenities, moderation pipeline.
*   `bookings/`: Booking model, status workflow, overlap-prevention logic.
*   `reviews/`: Reviews linked to completed bookings.
*   `notifications/`: In-app notification model and delivery.
*   `support/`: Helpdesk tickets and messages.
*   `analytics/`: Property view/search tracking, popular searches, scheduled retention cleanup.
*   `common/`: Shared choices, services, exception handling, health checks.
*   `locale/`: Translation files for English and German.
*   `docker-compose.yml` / `Dockerfile` / `entrypoint.sh`: Container orchestration and startup automation.
*   `manage.py`: Django management entry point.
