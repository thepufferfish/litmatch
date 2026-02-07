# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LitMatch is a book discovery and recommendation platform. It scrapes literary review data, processes it through an ETL pipeline, stores it in PostgreSQL with pgvector, serves a REST API, and provides a Streamlit UI for browsing and rating books.

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

### Docker Services
```bash
make create-db               # Start PostgreSQL container on litnet network
make start-api               # Build and start FastAPI backend (port 80)
make start-backend           # Full backend: DB + ETL + API
docker compose up --build -d # Start all services via compose
docker compose down          # Stop all services
```

### Individual Services
```bash
python -m backend.database   # Initialize database schema + pgvector extension
streamlit run frontend/main.py  # Start Streamlit frontend
```

## Architecture

```
Scraper (Scrapy) → books.jsonl → Dagster ETL → PostgreSQL+pgvector
                                                      ↓
                                              FastAPI Backend (port 80)
                                                      ↓
                                              Streamlit Frontend
```

**Five main components:**

- **`scraper/`** — Scrapy project that crawls bookmarks.reviews via sitemap spider. Uses rotating proxies and user-agent middleware. Outputs `books.jsonl`. Can be deployed to Scrapyd (port 6800).

- **`src/litmatch/`** — Dagster orchestration. Assets defined in `defs/assets.py` run a 4-stage ETL: extract (load jsonl) → raw_data (DataFrame) → cleaned_data (fix dates, classify fiction) → load_to_db (upsert into PostgreSQL with full relational model). Dagster root module is `litmatch`.

- **`backend/`** — FastAPI REST API. Models in `backend/db/models.py` use SQLModel. `backend/database.py` handles DB init and pgvector extension setup. Endpoints: auth (register/login), books, reviews, genres, ratings. Runs in Docker on port 80.

- **`frontend/`** — Streamlit app. `main.py` is the entry point, `api.py` wraps backend HTTP calls, `book_page.py` renders book details. Features: genre filtering, search, auth, rating submission.

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
- **`compose.yaml`** — Docker services: `db` (postgres:18 + pgvector), `backend` (FastAPI), `scrapyd`
- **`.env`** — PostgreSQL credentials and DATABASE_URL (used by both Makefile and compose)
- Docker network `litnet` is used for inter-container communication when running via Makefile
