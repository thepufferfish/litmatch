# LitMatch

A book discovery and recommendation platform. LitMatch scrapes literary review data from bookmarks.reviews, processes it through a Dagster ETL pipeline, stores it in PostgreSQL with pgvector, and serves a React frontend for browsing, searching, and rating books.

## Architecture

```
Scraper (Scrapy) --> books.jsonl --> Dagster ETL --> PostgreSQL + pgvector
                                                          |
                                                    FastAPI Backend
                                                          |
                                                    React Frontend
```

| Component | Stack | Location |
|-----------|-------|----------|
| Scraper | Scrapy, Scrapyd | `scraper/` |
| ETL | Dagster | `src/litmatch/` |
| Backend | FastAPI, SQLModel | `backend/` |
| Frontend | React, Vite, TypeScript, Tailwind CSS | `frontend/` |
| Recommender | SVD collaborative filtering (surprise) | `recommender/` |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- Podman and Podman Compose
- [uv](https://docs.astral.sh/uv/) (preferred Python package manager)

### 1. Install dependencies

```bash
uv sync
cd frontend && npm install && cd ..
```

### 2. Configure environment

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY (openssl rand -hex 32) and POSTGRES_PASSWORD
```

### 3. Start services

```bash
podman compose up --build -d
```

This starts PostgreSQL (port 5432), the FastAPI backend (port 8000), Scrapyd (port 6800), and the Dagster ETL pipeline (UI on port 3000).

### 4. Start the frontend

```bash
cd frontend && npm run dev
```

Open http://localhost:5173 to browse books.

## Development

### Running individual services

```bash
# Database only
podman compose up db -d

# Initialize schema (first time or after model changes)
python -m backend.database

# Backend API (containerized)
podman compose up backend -d

# Backend API (local dev, with auto-reload)
uv run uvicorn backend.app.main:app --reload --port 8000

# Frontend dev server (proxies /api to backend)
cd frontend && npm run dev

# Dagster ETL (containerized)
podman compose up dagster-code dagster-webserver dagster-daemon -d

# Dagster ETL UI (local dev, without containers)
uv run dg dev
```

### Testing

```bash
# Unit tests (Dagster pipeline)
make test-unit

# Integration tests (starts/stops compose stack)
make test-integration

# Frontend tests
cd frontend && npm test

# Coverage report
make test-coverage
```

### Service ports

| Service | Port |
|---------|------|
| PostgreSQL | 5432 |
| FastAPI Backend | 8000 (compose) / 80 (Makefile) |
| Scrapyd | 6800 |
| Dagster Code Server | 4000 |
| Dagster UI | 3000 |
| Frontend (nginx) | 8080 |
| Vite Dev Server | 5173 |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (verifies database connectivity) |
| POST | `/auth/register` | Create a new user |
| POST | `/auth/login` | Authenticate a user |
| POST | `/auth/refresh` | Refresh JWT access token (uses httpOnly cookie) |
| POST | `/auth/logout` | Clear refresh token cookie |
| GET | `/books/` | List books (paginated, filterable by genre/user) |
| GET | `/books/search` | Search books by title or author |
| GET | `/books/{book_id}` | Get a single book with details |
| GET | `/reviews/{book_id}` | Get reviews for a book |
| GET | `/genres/` | List all genres |
| GET | `/ratings/` | Get ratings (filterable by user/book) |
| POST | `/ratings/` | Create or update a rating |

API documentation is available at http://localhost:8000/docs when the backend is running.

## Database Schema

PostgreSQL with pgvector extension. Key entities defined in `backend/db/models.py`:

- **Book** -- central entity (title, author, publisher, isbn, description, fiction flag)
- **Author**, **Publisher** -- one-to-many with Book
- **Genre** -- many-to-many with Book via BookGenreLink
- **Review** -- linked to Book, Critic, and Publication
- **User**, **UserRating** -- authentication and book ratings

## Project Structure

```
litmatch/
  backend/                # FastAPI REST API
    app/
      main.py             #   API endpoints + CORS + rate limiting
      auth.py             #   JWT access/refresh token logic
      config.py           #   Environment variable configuration
      rate_limit.py       #   slowapi rate limiter setup
    db/models.py          #   SQLModel database models
    database.py           #   DB init + pgvector extension
    entrypoint.sh         #   Container startup script
    Dockerfile
  frontend/               # React SPA (Vite + TypeScript + Tailwind CSS v4)
    src/
      api/client.ts       #   Axios HTTP client
      components/         #   BookCard, BookGrid, SearchBar, StarRating, etc.
      context/            #   AuthContext (JWT auth)
      hooks/              #   TanStack React Query hooks (useBooks, useGenres, etc.)
      pages/              #   BrowsePage, BookDetailPage, LoginPage, RegisterPage
      types/              #   TypeScript type definitions
      utils/              #   Utility functions (slugify, validation)
  recommender/            # SVD collaborative filtering (surprise)
  scraper/                # Scrapy project (bookmarks.reviews)
  src/litmatch/           # Dagster ETL pipeline
    defs/
      assets/             #   Asset definitions (crawl, extract, validate, transform, load)
      resources/          #   Dagster resources (database, path, scrapyd)
      sensors/            #   Dagster sensors (data_freshness, startup_crawl)
      utils/              #   ETL utilities (db_operations, transforms, validation)
      jobs.py             #   Job definitions (etl_pipeline, crawl_and_load)
  tests/
    dagster/              #   Unit tests for Dagster assets, transforms, validation, sensors
    integration/          #   Integration tests (require running compose stack)
  compose.yaml            # Podman Compose services
  compose.test.yaml       # Override for integration tests
  Makefile                # Convenience targets
  pyproject.toml          # Python project config (hatchling)
  dagster.yaml            # Dagster instance config
  .env.example            # Environment variable template
```

## Further Reading

- [`docs/CONTRIB.md`](docs/CONTRIB.md) -- Development workflow and contributing guide
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) -- Deployment, monitoring, and troubleshooting
- [`docs/ROADMAP.md`](docs/ROADMAP.md) -- Project roadmap
