# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LitMatch is a book discovery and recommendation platform. It scrapes literary review data, processes it through an ETL pipeline, stores it in PostgreSQL with pgvector, serves a REST API, and provides a Streamlit UI for browsing and rating books. The goal of the platform is to grab critical reviews of books and allow users to rate those books and discover new books according to their taste. 

## Commands

### Setup
```bash
uv sync                      # Install dependencies (preferred)
pip install -e ".[dev]"      # Alternative: install with pip
```

### Dagster ETL
```bash
dg dev                       # Start Dagster UI at http://localhost:3000
```

### Container Services (Podman)
```bash
podman compose up --build -d       # Start all services (db, backend, scrapyd, dagster)
podman compose ps                  # Check service health status
podman compose logs -f backend     # Follow backend logs
podman compose logs -f dagster-code dagster-webserver dagster-daemon  # Dagster logs
podman compose down                # Stop all services
curl http://localhost:8000/health  # Verify backend + database connectivity
curl http://localhost:3000/server_info  # Verify Dagster webserver
make create-db                     # Start standalone PostgreSQL on litnet network
make start-api                     # Build and start FastAPI backend (port 80)
make start-backend                 # Full standalone backend: DB + ETL + API
```

### Testing
```bash
make test-unit               # Run unit tests (no containers required)
make test-integration        # Start test stack, run integration tests, tear down
make test-integration-up     # Start the integration test compose stack only
make test-integration-down   # Tear down the integration test compose stack
make test-all                # Run unit + integration tests
make test-coverage           # Run unit tests with coverage report
uv run pytest tests/dagster/ -v                  # Run all dagster unit tests
uv run pytest tests/integration/ -v -m integration  # Run integration tests (stack must be up)
```

### Individual Services
```bash
python -m backend.database   # Initialize database schema + pgvector extension
cd frontend && npm run dev   # Start React frontend (Vite dev server, port 5173)
```

## Architecture

```
Scraper (Scrapy) → books.jsonl → Dagster ETL → PostgreSQL+pgvector
                                                      ↓
                                              FastAPI Backend (port 8000)
                                                      ↓
                                              React SPA (Vite, port 5173)
```

**Five main components:**

- **`scraper/`** — Scrapy project that crawls bookmarks.reviews via sitemap spider. Uses rotating proxies and user-agent middleware. Outputs `books.jsonl`. Can be deployed to Scrapyd (port 6800).

- **`src/litmatch/`** — Dagster orchestration. Modular assets in `defs/assets/` run a 4-stage ETL: raw_books (parse jsonl) -> validate_raw_books (field validation) -> cleaned_books (transform dates, ratings, fiction flag) -> load_books (upsert to PostgreSQL). Resources in `defs/resources/`, sensors in `defs/sensors/`, utilities in `defs/utils/`. Two sensors: `data_freshness_sensor` (ongoing file-watch, triggers ETL when books.jsonl is modified) and `startup_etl_sensor` (fires exactly once on first deployment if books.jsonl exists, seeds the database automatically). Dagster root module is `litmatch`.

- **`backend/`** — FastAPI REST API. Models in `backend/db/models.py` use SQLModel. `backend/database.py` handles DB init and pgvector extension setup. Endpoints: auth (register/login/refresh), books, reviews, genres, ratings. Config in `backend/app/config.py` reads env vars. Runs in Podman on port 8000 (compose) or port 80 (Makefile standalone).

- **`frontend/`** — React SPA (Vite + TypeScript + Tailwind CSS v4). Entry point is `src/main.tsx`, API client in `src/api/client.ts`, pages under `src/pages/`, components under `src/components/`. Uses TanStack React Query for data fetching, react-router v7 for routing, AuthContext for JWT auth. The Vite dev server proxies `/api/*` to the backend on port 8000 (stripping the `/api` prefix).

- **`recommender/`** — SVD-based collaborative filtering using the `surprise` library.

## Database Schema

PostgreSQL with pgvector. Key entities defined in `backend/db/models.py`:
- **Book** — central entity (title, author, publisher, isbn, description, fiction flag)
- **Author**, **Publisher** — one-to-many with Book
- **Genre** — many-to-many with Book via BookGenreLink
- **Review** — linked to Book, Critic, and Publication
- **User**, **UserRating** — authentication and book ratings

## Key Configuration

- **Python 3.12+** required (`.python-version`)
- **`pyproject.toml`** — all dependencies, build config (hatchling), Dagster `dg` tool config
- **`dagster.yaml`** — Dagster instance config (logging)
- **`compose.yaml`** — Podman Compose services: `db` (postgres:18 + pgvector), `backend` (FastAPI), `scrapyd`, `dagster-code` (gRPC code server), `dagster-webserver` (UI on port 3000), `dagster-daemon` (schedules/sensors). All services have health checks; backend and Dagster wait for healthy database before starting. The dagster-daemon depends on `backend: service_healthy` (not db directly) to ensure DB schema is initialized before the startup_etl_sensor runs.
- **`compose.test.yaml`** — Override for integration tests. Disables frontend/scrapyd, mounts test fixtures into dagster containers, uses isolated volumes. Use with `make test-integration`.
- **`.env`** — PostgreSQL credentials, DATABASE_URL, SECRET_KEY, CORS_ORIGINS, auth cookie config (used by both Makefile and compose). See `.env.example` for all variables.
- Podman network `litnet` is used for inter-container communication when running via Makefile

## Test Structure

```
tests/
  dagster/              # Unit tests for Dagster assets, transforms, validation, sensors
    test_assets.py      # Asset pipeline tests (extract, validate, transform, load)
    test_db_operations.py  # Database upsert operation tests
    test_transforms.py  # Data transformation tests
    test_validation.py  # Input validation tests
    test_sensors.py     # Data freshness sensor tests
    test_startup_sensor.py  # Startup ETL sensor tests (one-time seed)
  integration/          # Integration tests (require running compose stack)
    fixtures/books.jsonl  # 3 sample book records for test data
    conftest.py         # Session-scoped compose stack fixtures
    helpers.py          # HTTP wait, health check, compose command utilities
    test_container_health.py  # Service health and port reachability
    test_database.py    # Schema initialization and connectivity
    test_etl_pipeline.py     # Full ETL pipeline execution via GraphQL API
    test_backend_api.py      # REST API endpoints (auth, books, search, ratings)
```
