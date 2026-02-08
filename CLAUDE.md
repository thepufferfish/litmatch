# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LitMatch is a book discovery and recommendation platform. It scrapes literary review data, processes it through an ETL pipeline, stores it in PostgreSQL with pgvector, serves a REST API, and provides a React SPA for browsing and rating books.

## Commands

### Setup
```bash
uv sync                      # Install dependencies (preferred)
pip install -e ".[dev]"      # Alternative: install with pip
cd frontend && npm install   # Install frontend dependencies
```

### Dagster ETL
```bash
dg dev                       # Start Dagster UI at http://localhost:3000
```

### Frontend (React)
```bash
cd frontend
npm run dev                  # Start Vite dev server at http://localhost:5173
npm run build               # TypeScript check + production build
npm run test                # Run Vitest test suite
npm run test:watch          # Run tests in watch mode
```

### Docker Services
```bash
make create-db               # Start PostgreSQL container on litnet network
make start-api               # Build and start FastAPI backend (port 80 via Makefile)
make start-backend           # Full backend: DB + ETL + API
docker compose up --build -d # Start all services via compose (backend on port 8000)
docker compose down          # Stop all services
```

### Individual Services
```bash
python -m backend.database   # Initialize database schema + pgvector extension
```

### Testing
```bash
uv run pytest                # Run backend Python tests
cd frontend && npm test      # Run frontend Vitest tests
```

## Architecture

```
Scraper (Scrapy) → books.jsonl → Dagster ETL → PostgreSQL+pgvector
                                                      ↓
                                              FastAPI Backend (port 8000)
                                                      ↓
                                              React Frontend (port 5173)
```

**Five main components:**

- **`scraper/`** — Scrapy project that crawls bookmarks.reviews via sitemap spider. Uses rotating proxies and user-agent middleware. Outputs `books.jsonl`. Can be deployed to Scrapyd (port 6800).

- **`src/litmatch/`** — Dagster orchestration. Assets defined in `defs/assets.py` run a 4-stage ETL: extract (load jsonl) → raw_data (DataFrame) → cleaned_data (fix dates, classify fiction) → load_to_db (upsert into PostgreSQL with full relational model). Dagster root module is `litmatch`.

- **`backend/`** — FastAPI REST API. Models in `backend/db/models.py` use SQLModel. `backend/database.py` handles DB init and pgvector extension setup. Endpoints: auth (register/login), books, search, reviews, genres, ratings. Runs in Docker on port 8000.

- **`frontend/`** — React SPA (Vite + TypeScript + Tailwind CSS + React Router + TanStack React Query). Entry point `src/main.tsx`. Pages: BrowsePage, BookDetailPage. Components: BookCard, BookGrid, GenreSidebar, SearchBar, Pagination, ReviewList, Skeleton, ErrorBoundary. Legacy Streamlit files (`main.py`, `api.py`, `book_page.py`) still present but being replaced. See `SPEC.md` for the frontend rewrite spec and `PLAN.md` for implementation plan.

- **`recommender/`** — SVD-based collaborative filtering using the `surprise` library.

## Database Schema

PostgreSQL with pgvector. Key entities defined in `backend/db/models.py`:
- **Book** — central entity (title, author, publisher, publish_date, description, url, cover)
- **Author**, **Publisher** — one-to-many with Book
- **Genre** — many-to-many with Book via BookGenreLink
- **Review** — linked to Book, Critic, and Publication
- **User**, **UserRating** — authentication and book ratings

## Key Configuration

- **Python 3.12+** required (`.python-version`)
- **`pyproject.toml`** — all dependencies, build config (hatchling), Dagster `dg` tool config
- **`dagster.yaml`** — Dagster instance config (logging)
- **`compose.yaml`** — Docker services: `db` (pgvector/pgvector:pg18), `backend` (FastAPI on port 8000), `scrapyd`
- **`.env`** — PostgreSQL credentials and DATABASE_URL (used by both Makefile and compose)
- **`SPEC.md`** — React frontend implementation spec (Phases 1-3: Browse, Auth & Ratings, Recommendations)
- **`PLAN.md`** — Detailed implementation plan with dependency graph and success criteria
- Docker network `litnet` is used for inter-container communication when running via Makefile

## Gotchas

- **Vite dev proxy**: `frontend/vite.config.ts` proxies `/api` requests to `http://localhost:8000`, stripping the `/api` prefix. Frontend API calls use `/api/...` paths; backend routes have no `/api` prefix.
- **Orphaned Dagster assets**: `raw_data` and `cleaned_data` assets (plus `fix_publish_dates`, `check_if_fiction`, `add_fiction_flag` helpers) are disconnected from the active `extract` -> `load_to_db` pipeline. Kept intentionally for potential future use.
- **Large etl.log**: A ~200MB `etl.log` file exists in the project root. It's gitignored via `*.log` but watch out when running tools that scan all files.
- **Port mismatch**: Makefile `start-api` exposes port 80, but `compose.yaml` exposes port 8000. Use compose for development.
