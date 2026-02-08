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
- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (preferred Python package manager)

### 1. Install dependencies

```bash
uv sync
cd frontend && npm install && cd ..
```

### 2. Configure environment

Create a `.env` file in the project root:

```
POSTGRES_DB=bookdb
POSTGRES_USER=bookuser
POSTGRES_PASSWORD=bookpassword
DATABASE_URL=postgresql://bookuser:bookpassword@localhost:5432/bookdb
```

### 3. Start services

```bash
docker compose up --build -d
```

This starts PostgreSQL (port 5432), the FastAPI backend (port 8000), and Scrapyd (port 6800).

### 4. Start the frontend

```bash
cd frontend && npm run dev
```

Open http://localhost:5173 to browse books.

## Development

### Running individual services

```bash
# Database only
docker compose up db -d

# Initialize schema (first time or after model changes)
python -m backend.database

# Backend API
docker compose up backend -d

# Frontend dev server (proxies /api to backend)
cd frontend && npm run dev

# Dagster ETL UI
dg dev
```

### Testing

```bash
# Backend
uv run pytest

# Frontend
cd frontend && npm test
```

### Service ports

| Service | Port |
|---------|------|
| PostgreSQL | 5432 |
| FastAPI Backend | 8000 |
| Scrapyd | 6800 |
| Dagster UI | 3000 |
| Vite Dev Server | 5173 |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create a new user |
| POST | `/auth/login` | Authenticate a user |
| GET | `/books/` | List books (paginated, filterable by genre/user) |
| GET | `/books/search` | Search books by title or author |
| GET | `/books/{id}` | Get a single book |
| GET | `/reviews/{book_id}` | Get reviews for a book |
| GET | `/genres/` | List all genres |
| GET | `/ratings/` | Get ratings (filterable by user/book) |
| POST | `/ratings/` | Create or update a rating |

API documentation is available at http://localhost:8000/docs when the backend is running.

## Database Schema

PostgreSQL with pgvector. Key entities defined in `backend/db/models.py`:

- **Book** -- title, author, publisher, publish_date, description, url, cover
- **Author**, **Publisher** -- one-to-many with Book
- **Genre** -- many-to-many with Book via BookGenreLink
- **Review** -- linked to Book, Critic, and Publication
- **User**, **UserRating** -- authentication and book ratings

## Project Structure

```
litmatch/
  backend/                # FastAPI REST API
    app/main.py           #   API endpoints
    db/models.py          #   SQLModel database models
    database.py           #   DB init + pgvector extension
    Dockerfile
    tests/
  frontend/               # React SPA
    src/
      api/client.ts       #   Axios HTTP client
      components/         #   BookCard, BookGrid, SearchBar, etc.
      hooks/              #   TanStack React Query hooks
      pages/              #   BrowsePage, BookDetailPage
      types/              #   TypeScript type definitions
      utils/              #   Utility functions + tests
  recommender/            # SVD collaborative filtering
  scraper/                # Scrapy project (bookmarks.reviews)
  src/litmatch/           # Dagster ETL pipeline
    defs/assets.py        #   Asset definitions (extract, load_to_db)
    defs/resources.py     #   Dagster resources
  compose.yaml            # Docker services
  Makefile                # Convenience targets
  pyproject.toml          # Python project config (hatchling)
  dagster.yaml            # Dagster instance config
```

## Further Reading

- [`docs/CONTRIB.md`](docs/CONTRIB.md) -- Development workflow and contributing guide
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) -- Deployment, monitoring, and troubleshooting
- [`SPEC.md`](SPEC.md) -- Frontend implementation spec
- [`PLAN.md`](PLAN.md) -- Implementation plan with dependency graph
