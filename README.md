# Advanced Dynamic Survey Platform

Enterprise-level survey platform for designing, deploying, and analysing custom surveys.
Supports complex conditional logic, high-traffic volumes, role-based access control (RBAC), and real-time analytics.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Local Setup (without Docker)](#local-setup-without-docker)
- [Docker Setup](#docker-setup)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
- [API Overview](#api-overview)
- [Response Envelope](#response-envelope)
- [Authentication](#authentication)
- [Roles & Permissions](#roles--permissions)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | Django 4.2 + Django REST Framework 3.14 |
| Database | PostgreSQL 15 |
| Cache / Broker | Redis 7 |
| Task Queue | Celery 5 |
| Auth | JWT — `djangorestframework-simplejwt` |
| Docs | drf-spectacular (OpenAPI 3 / Swagger UI) |
| Testing | pytest + pytest-django + factory_boy |
| Containerisation | Docker + docker-compose |
| CI | GitHub Actions |

---

## Local Setup (without Docker)

### Prerequisites

- Python 3.11+
- PostgreSQL 15
- Redis 7

### Steps

```bash
# 1. Clone the repo
git clone <repo-url>
cd dynamic_survey_app

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements/development.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — at minimum set DB_NAME, DB_USER, DB_PASSWORD, SECRET_KEY, ENCRYPTION_KEY

# 5. Generate an ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the output into ENCRYPTION_KEY in .env

# 6. Apply database migrations
python manage.py migrate

# 7. Create a superuser (optional)
python manage.py createsuperuser

# 8. Run the development server
python manage.py runserver
```

The API is now available at `http://localhost:8000/api/v1/`.
Swagger UI is at `http://localhost:8000/api/v1/docs/`.

### Start Celery workers (separate terminals)

```bash
# Worker
celery -A config worker --loglevel=info

# Beat scheduler (periodic tasks)
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Flower monitoring UI (optional)
celery -A config flower --port=5555
```

---

## Docker Setup

### Prerequisites

- Docker 24+
- Docker Compose v2

### Quick start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env — update secrets as needed

# 2. Build images and start all services
docker compose up --build

# 3. (First run only) Migrations run automatically via the `init` service.
#    To run manually:
docker compose run --rm web python manage.py migrate

# 4. Create a superuser
docker compose run --rm web python manage.py createsuperuser
```

The stack runs at:

| Service | URL |
|---|---|
| API | `http://localhost:8000/api/v1/` |
| Swagger UI | `http://localhost:8000/api/v1/docs/` |
| ReDoc | `http://localhost:8000/api/v1/redoc/` |
| Django Admin | `http://localhost:8000/admin/` |
| Flower | `http://localhost:5555/` |

### Common Docker commands

```bash
# Tail logs for a specific service
docker compose logs -f web

# Run management commands
docker compose run --rm web python manage.py <command>

# Run tests inside the container
docker compose run --rm web pytest

# Stop all services and remove volumes
docker compose down -v

# Rebuild after dependency changes
docker compose build
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values. All variables are required unless marked optional.

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key (long random string) | `change-me-...` |
| `DEBUG` | Enable Django debug mode | `True` / `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1` |
| `DJANGO_SETTINGS_MODULE` | Settings module to use | `config.settings.development` |
| `DB_NAME` | PostgreSQL database name | `survey_platform` |
| `DB_USER` | PostgreSQL user | `survey_user` |
| `DB_PASSWORD` | PostgreSQL password | `survey_password` |
| `DB_HOST` | PostgreSQL host | `db` (Docker) / `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_SSLMODE` | PostgreSQL SSL mode | `disable` / `prefer` / `require` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL (usually Redis) | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://redis:6379/0` |
| `ENCRYPTION_KEY` | Fernet key for sensitive field encryption | `<base64-url-safe-32-byte-key>` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins | `http://localhost:3000` |
| `EMAIL_BACKEND` | Django email backend | `django.core.mail.backends.console.EmailBackend` |
| `EMAIL_HOST` | SMTP host (optional) | `smtp.example.com` |
| `EMAIL_PORT` | SMTP port (optional) | `587` |
| `EMAIL_HOST_USER` | SMTP user (optional) | `user@example.com` |
| `EMAIL_HOST_PASSWORD` | SMTP password (optional) | `secret` |
| `EMAIL_USE_TLS` | Enable TLS for SMTP | `True` |
| `DEFAULT_FROM_EMAIL` | Default sender address | `noreply@survey-platform.com` |
| `FLOWER_USER` | Flower UI basic-auth username | `admin` |
| `FLOWER_PASSWORD` | Flower UI basic-auth password | `admin` |

Generate a `SECRET_KEY`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Generate an `ENCRYPTION_KEY`:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Running Tests

```bash
# Run the full test suite with coverage
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run with a specific test file
pytest tests/unit/test_survey_service.py

# Skip coverage enforcement
pytest --no-cov
```

Coverage target is **85 %**. The `--cov-fail-under=85` flag in `pytest.ini` enforces this.

---

## API Overview

All endpoints are prefixed with `/api/v1/`. Authentication uses `Bearer <access_token>` in the `Authorization` header.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register/` | Register a new user |
| `POST` | `/api/v1/auth/login/` | Obtain JWT access + refresh tokens |
| `POST` | `/api/v1/auth/refresh/` | Rotate a refresh token |
| `GET` | `/api/v1/auth/profile/` | Get own profile |
| `PATCH` | `/api/v1/auth/profile/` | Update own profile |
| `GET` | `/api/v1/auth/users/` | List all users (admin only) |
| `GET` | `/api/v1/auth/users/{id}/` | Get a user (admin only) |
| `PATCH` | `/api/v1/auth/users/{id}/` | Update a user (admin only) |
| `DELETE` | `/api/v1/auth/users/{id}/` | Delete a user (admin only) |

### Surveys

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/surveys/` | List all surveys |
| `POST` | `/api/v1/surveys/` | Create a survey |
| `GET` | `/api/v1/surveys/{id}/` | Get survey detail (cached) |
| `PUT` | `/api/v1/surveys/{id}/` | Update a survey |
| `DELETE` | `/api/v1/surveys/{id}/` | Delete a survey |
| `POST` | `/api/v1/surveys/{id}/publish/` | Publish a draft survey |
| `POST` | `/api/v1/surveys/{id}/clone/` | Clone a survey |

### Sections

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/surveys/{survey_id}/sections/` | List sections |
| `POST` | `/api/v1/surveys/{survey_id}/sections/` | Create a section |
| `PUT` | `/api/v1/surveys/{survey_id}/sections/{id}/` | Update a section |
| `DELETE` | `/api/v1/surveys/{survey_id}/sections/{id}/` | Delete a section |

### Fields

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/sections/{section_id}/fields/` | List fields |
| `POST` | `/api/v1/sections/{section_id}/fields/` | Create a field |
| `PUT` | `/api/v1/sections/{section_id}/fields/{id}/` | Update a field |
| `DELETE` | `/api/v1/sections/{section_id}/fields/{id}/` | Delete a field |

### Conditions

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/fields/{field_id}/conditions/` | Create a condition |
| `DELETE` | `/api/v1/conditions/{id}/` | Delete a condition |

### Responses

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/surveys/{survey_id}/respond/` | Submit or partially save a response |
| `GET` | `/api/v1/responses/{session_token}/resume/` | Resume a partial session |
| `GET` | `/api/v1/responses/mine/` | Get own responses (authenticated) |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/surveys/{id}/analytics/` | Survey-level aggregated stats |
| `GET` | `/api/v1/surveys/{id}/analytics/fields/` | Per-field answer distribution |
| `POST` | `/api/v1/surveys/{id}/export/` | Queue async response export (CSV/JSON) |
| `POST` | `/api/v1/surveys/{id}/report/` | Queue async analytics report |
| `GET` | `/api/v1/tasks/{task_id}/status/` | Poll async task status |

### Audit

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/audit/logs/` | List audit logs (admin only) |

### Invitations

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/surveys/{id}/invite/` | Send survey invitations via email |

---

## Response Envelope

Every endpoint returns a consistent JSON envelope:

```json
{
  "success": true,
  "data": {},
  "message": "Human-readable status message.",
  "errors": null
}
```

On error:

```json
{
  "success": false,
  "data": null,
  "message": "Error description.",
  "errors": {
    "field_name": ["Validation error detail."]
  }
}
```

---

## Authentication

- JWT access tokens expire in **15 minutes**.
- JWT refresh tokens expire in **7 days** and rotate on use (old tokens are blacklisted).
- Include the access token in every request header:
  ```
  Authorization: Bearer <access_token>
  ```

---

## Roles & Permissions

| Role | Surveys | Analytics | Raw Responses | Audit Logs | User Management |
|---|---|---|---|---|---|
| `admin` | Full CRUD | Read + Export | Read | Read | Full CRUD |
| `analyst` | Read | Read + Export | No | No | No |
| `data_viewer` | Read | Read | No | No | No |

- Survey owners can always edit/delete their own surveys regardless of role.
- Rate limiting applies to `/auth/register/` and `/auth/login/`: **5 requests / minute per IP**.
