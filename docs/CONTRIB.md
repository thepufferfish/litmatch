# Contributing to LitMatch

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (preferred Python package manager)

## Environment Setup

### 1. Clone and install Python dependencies

```bash
git clone <repo-url>
cd litmatch
uv sync
```

### 2. Install frontend dependencies

```bash
cd frontend && npm install
```

### 3. Configure environment variables

Create a `.env` file in the project root:

| Variable | Purpose | Example |
|----------|---------|---------|
| `POSTGRES_DB` | PostgreSQL database name | `bookdb` |
| `POSTGRES_USER` | PostgreSQL username | `bookuser` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `bookpassword` |
| `DATABASE_URL` | Full connection string (used by backend + Dagster) | `postgresql://bookuser:bookpassword@localhost:5432/bookdb` |
| `PROXY_TOKEN` | Proxy service token for scraper | *(required for scraping)* |

### 4. Start the database

```bash
docker compose up db -d
```

### 5. Initialize the database schema

```bash
python -m backend.database
```

## Available Scripts

### Python / Backend

| Command | Description |
|---------|-------------|
| `uv sync` | Install/sync Python dependencies |
| `uv run pytest` | Run backend test suite |
| `dg dev` | Start Dagster UI at http://localhost:3000 |
| `python -m backend.database` | Initialize DB schema + pgvector extension |

### Frontend (run from `frontend/`)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server at http://localhost:5173 |
| `npm run build` | TypeScript check + production build |
| `npm run preview` | Preview production build locally |
| `npm run test` | Run Vitest test suite (single run) |
| `npm run test:watch` | Run Vitest in watch mode |

### Docker / Infrastructure

| Command | Description |
|---------|-------------|
| `docker compose up --build -d` | Start all services (db, backend, scrapyd) |
| `docker compose down` | Stop all services |
| `docker compose up db -d` | Start only PostgreSQL |
| `make create-db` | Start standalone PostgreSQL container on litnet network |
| `make start-api` | Build and start FastAPI backend (port 80, standalone) |
| `make start-backend` | Full standalone backend: DB + schema init + API |

## Development Workflow

### Running the full stack locally

1. Start the database:
   ```bash
   docker compose up db -d
   ```

2. Initialize the schema (first time or after model changes):
   ```bash
   python -m backend.database
   ```

3. Start the backend API:
   ```bash
   docker compose up backend -d
   # Backend available at http://localhost:8000
   ```

4. Start the frontend dev server:
   ```bash
   cd frontend && npm run dev
   # Frontend available at http://localhost:5173
   # API requests to /api/* are proxied to localhost:8000
   ```

5. (Optional) Start Dagster for ETL:
   ```bash
   dg dev
   # Dagster UI at http://localhost:3000
   ```

### Running with Docker Compose (all services)

```bash
docker compose up --build -d
```

This starts:
- **db** (pgvector/pgvector:pg18) on port 5432
- **backend** (FastAPI) on port 8000
- **scrapyd** (Scrapy daemon) on port 6800

## Testing

### Backend (Python)

```bash
uv run pytest
```

Tests are in `backend/tests/`. Use pytest markers for categorization:
- `@pytest.mark.unit` for unit tests
- `@pytest.mark.integration` for integration tests

### Frontend (TypeScript)

```bash
cd frontend
npm run test          # Single run
npm run test:watch    # Watch mode
```

Tests are colocated with source files (e.g., `SearchBar.test.tsx`, `slugify.test.ts`). The test environment uses jsdom with a setup file at `src/test/setup.ts`.

## Project Structure

```
litmatch/
  backend/              # FastAPI REST API
    app/main.py         # API endpoints
    db/models.py        # SQLModel database models
    database.py         # DB initialization + pgvector setup
    Dockerfile          # Backend container
    tests/              # Backend tests
  frontend/             # React SPA (Vite + TypeScript + Tailwind)
    src/
      api/client.ts     # Axios HTTP client
      components/       # Reusable UI components
      hooks/            # TanStack React Query hooks
      pages/            # Route page components
      types/            # TypeScript type definitions
      utils/            # Utility functions
  recommender/          # SVD collaborative filtering (surprise)
  scraper/              # Scrapy project for bookmarks.reviews
  src/litmatch/         # Dagster ETL pipeline
    defs/assets.py      # Dagster asset definitions
    defs/resources.py   # Dagster resources
  compose.yaml          # Docker Compose services
  Makefile              # Convenience targets
  pyproject.toml        # Python project config
  dagster.yaml          # Dagster instance config
```

## API Proxy Configuration

The frontend Vite dev server proxies `/api` requests to the backend:
- Frontend calls: `GET /api/books/`
- Proxy rewrites to: `GET http://localhost:8000/books/`

The `/api` prefix is **stripped** before forwarding. Backend routes have **no** `/api` prefix.

## Code Style

- **Python**: PEP 8, type annotations on all function signatures, format with black/ruff
- **TypeScript**: Strict mode, Tailwind CSS for styling
- **Immutability**: Prefer creating new objects over mutation
- **Error handling**: Handle errors explicitly; never silently swallow exceptions
