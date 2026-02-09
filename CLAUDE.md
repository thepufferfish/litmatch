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
podman compose up --build -d       # Start all services (db, backend, scrapyd)
podman compose ps                  # Check service health status
podman compose logs -f backend     # Follow backend logs
podman compose down                # Stop all services
curl http://localhost:8000/health  # Verify backend + database connectivity
make create-db                     # Start standalone PostgreSQL on litnet network
make start-api                     # Build and start FastAPI backend (port 80)
make start-backend                 # Full standalone backend: DB + ETL + API
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

- **`src/litmatch/`** — Dagster orchestration. Modular assets in `defs/assets/` run a 4-stage ETL: raw_books (parse jsonl) → validate_raw_books (field validation) → cleaned_books (transform dates, ratings, fiction flag) → load_books (upsert to PostgreSQL). Resources in `defs/resources/`, utilities in `defs/utils/`. Dagster root module is `litmatch`.

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
- **`compose.yaml`** — Podman Compose services: `db` (postgres:18 + pgvector), `backend` (FastAPI), `scrapyd`. All services have health checks; backend waits for healthy database before starting.
- **`.env`** — PostgreSQL credentials, DATABASE_URL, SECRET_KEY, CORS_ORIGINS, auth cookie config (used by both Makefile and compose). See `.env.example` for all variables.
- Podman network `litnet` is used for inter-container communication when running via Makefile
