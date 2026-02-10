# Contributing to LitMatch

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- Podman and Podman Compose
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

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
```

#### Environment Variables Reference

| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `POSTGRES_DB` | PostgreSQL database name | **Yes** | `bookdb` |
| `POSTGRES_USER` | PostgreSQL username | **Yes** | `bookuser` |
| `POSTGRES_PASSWORD` | PostgreSQL password | **Yes** | `changeme` |
| `DATABASE_URL` | Full PostgreSQL connection string for backend + Dagster | **Yes** | `postgresql://bookuser:changeme@db:5432/bookdb` |
| `SECRET_KEY` | JWT signing key for auth tokens (generate with: `openssl rand -hex 32`) | **Yes** | `changeme` |
| `CORS_ORIGINS` | Comma-separated allowed origins (include Vite dev server and nginx origins) | No | `http://localhost:5173,http://localhost:8080` |
| `COOKIE_SECURE` | Set refresh cookie as Secure (use `false` for local dev without TLS) | No | `false` |
| `REFRESH_COOKIE_PATH` | Path scope for refresh tokens (`/api/auth/refresh` for nginx proxy, `/auth/refresh` for direct backend) | No | `/api/auth/refresh` |
| `PROXY_TOKEN` | Rotating proxy service token for scraper | For scraping | — |
| `SCRAPYD_URL` | Scrapyd API URL (used by Dagster to trigger crawl jobs; `scrapyd` for compose, `localhost` for local dev) | No | `http://scrapyd:6800` |
| `RAW_DATA_DIR` | Path to raw data directory (set automatically in compose.yaml) | No | `/data/raw` |
| `EMBEDDING_MODEL_NAME` | Sentence-transformers model for review embeddings | No | `all-MiniLM-L6-v2` |

**Connection String Notes:**
- For compose deployment: use `db` as hostname (container name)
- For local development: use `localhost` as hostname

### 4. Start the database

```bash
podman compose up db -d
```

### 5. Initialize the database schema

```bash
python -m backend.database
```

## Available Scripts

### Make Commands (root directory)

| Command | Description |
|---------|-------------|
| `make up` | Start all services via Podman Compose (db, backend, scrapyd, dagster) |
| `make down` | Stop all services |
| `make logs` | Follow logs for all services |
| `make backend-shell` | Open bash shell in backend container |
| `make db-shell` | Open psql shell in database container |
| `make run-spider` | Schedule spider via Scrapyd (scrapes bookmarks.reviews) |
| `make dagster-logs` | Follow Dagster service logs (code server, webserver, daemon) |
| `make clean` | Stop all services and remove volumes |
| `make rebuild` | Clean and rebuild all services from scratch |
| `make create-db` | Start standalone PostgreSQL on litnet network |
| `make start-api` | Build and start FastAPI backend (port 80, standalone) |
| `make start-frontend` | Build and start frontend nginx container (port 8080) |
| `make stop-frontend` | Stop and remove frontend container |
| `make start-backend` | Full standalone backend: DB + schema init + API |
| `make start-all` | Start both backend and frontend (standalone) |
| `make test-unit` | Run unit tests (no containers required) |
| `make test-integration` | Start test stack, run integration tests, tear down |
| `make test-integration-up` | Start the integration test compose stack only |
| `make test-integration-down` | Tear down the integration test compose stack |
| `make test-all` | Run unit + integration tests |
| `make test-coverage` | Run unit tests with coverage report |

### Python / Backend

| Command | Description |
|---------|-------------|
| `uv sync` | Install/sync Python dependencies |
| `uv run pytest tests/dagster/ -v` | Run all Dagster unit tests |
| `uv run pytest tests/integration/ -v -m integration` | Run integration tests (stack must be up) |
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

### Podman / Infrastructure

| Command | Description |
|---------|-------------|
| `podman compose up --build -d` | Start all services (db, backend, scrapyd, dagster) |
| `podman compose down` | Stop all services |
| `podman compose ps` | Check service health status |
| `podman compose logs -f backend` | Follow backend logs |
| `podman compose up db -d` | Start only PostgreSQL |

## Development Workflow

### Running the full stack locally

1. Start the database:
   ```bash
   podman compose up db -d
   ```

2. Initialize the schema (first time or after model changes):
   ```bash
   python -m backend.database
   ```

3. Start the backend API:
   ```bash
   podman compose up backend -d
   # Backend available at http://localhost:8000
   # Health check: curl http://localhost:8000/health
   ```

4. Start the frontend dev server:
   ```bash
   cd frontend && npm run dev
   # Frontend available at http://localhost:5173
   # API requests to /api/* are proxied to localhost:8000
   ```

5. (Optional) Start Dagster for ETL:
   ```bash
   podman compose up dagster-code dagster-webserver dagster-daemon -d
   # Dagster UI at http://localhost:3000
   # Verify: curl http://localhost:3000/server_info
   ```

### Running with Podman Compose (all services)

```bash
make up
# or
podman compose up --build -d
```

This starts:
- **db** (pgvector/pgvector:pg18) on port 5432
- **backend** (FastAPI) on port 8000
- **scrapyd** (Scrapy daemon) on port 6800
- **dagster-code** (gRPC code server) on port 4000
- **dagster-webserver** (UI) on port 3000
- **dagster-daemon** (schedules/sensors)
- **frontend** (nginx) on port 8080

All services have health checks. The backend waits for healthy database before starting. The dagster-daemon waits for both healthy dagster-code and healthy backend to ensure database is initialized before the startup crawl sensor runs.

## Testing

### Unit Tests (Dagster)

```bash
make test-unit
# or
uv run pytest tests/dagster/ -v -m "not integration"
```

Tests are in `tests/dagster/`:
- `test_assets.py` — Asset pipeline tests (extract, validate, transform, load)
- `test_asset_dependencies.py` — Asset dependency graph tests
- `test_crawl_asset.py` — Crawl asset + jobs module tests
- `test_db_operations.py` — Database upsert operation tests
- `test_scrapyd_resource.py` — ScrapydResource HTTP client tests
- `test_sensors.py` — Data freshness sensor tests
- `test_startup_crawl_sensor.py` — Startup crawl sensor state machine tests
- `test_transforms.py` — Data transformation tests
- `test_validation.py` — Input validation tests
- `test_embedding_asset.py` — Review embedding asset tests
- `test_book_embedding_asset.py` — Book embedding asset tests
- `test_embedding_resource.py` — EmbeddingModelResource tests
- `test_schedule.py` — Weekly ETL schedule tests
- `test_retry_policy.py` — Asset retry policy tests
- `test_metadata_emission.py` — Asset metadata emission tests
- `test_quarantine.py` — Quarantine tests

### Backend Tests

```bash
uv run pytest backend/tests/ -v
```

Tests are in `backend/tests/`:
- `test_recommendations.py` — Recommendation engine tests (embedding computation, nearest-book search, popular fallback)

### Integration Tests

```bash
make test-integration
# or
make test-integration-up               # Start test stack
uv run pytest tests/integration/ -v -m integration --tb=short
make test-integration-down             # Tear down
```

Tests are in `tests/integration/`:
- `test_container_health.py` — Service health and port reachability
- `test_database.py` — Schema initialization and connectivity
- `test_etl_pipeline.py` — Full ETL pipeline execution via GraphQL API
- `test_backend_api.py` — REST API endpoints (auth, books, search, ratings)

**Test fixtures:** `tests/integration/fixtures/books.jsonl` contains 3 sample book records mounted into Dagster containers during integration tests.

**Integration test configuration (`compose.test.yaml`):**
- Uses isolated test volumes: `postgres_data_test`, `dagster_storage_test` (independent from dev volumes)
- Mounts `./tests/integration/fixtures` -> `/data/raw` (same as production path)
- Sets `SCRAPYD_URL=http://scrapyd-disabled:6800` (unreachable host) to keep startup_crawl_sensor idle
- Sets `RAW_DATA_DIR=/data/raw` (no nested `/raw` subdirectory) to match fixture mount
- Disables `frontend` and `scrapyd` services (not needed for integration tests)
- Removes scrapyd dependency from dagster-code (prevents waiting for disabled service)

### Frontend Tests (TypeScript)

```bash
cd frontend
npm run test          # Single run
npm run test:watch    # Watch mode
```

Tests are colocated with source files (e.g., `SearchBar.test.tsx`, `slugify.test.ts`). The test environment uses jsdom with a setup file at `src/test/setup.ts`.

### Coverage Report

```bash
make test-coverage
# or
uv run pytest tests/dagster/ -v --cov=litmatch --cov-report=term-missing -m "not integration"
```

## Project Structure

```
litmatch/
  backend/              # FastAPI REST API
    app/
      main.py           # API endpoints + CORS + rate limiting
      auth.py           # JWT access/refresh token logic
      config.py         # Environment variable configuration
      queries.py        # Shared SQL query builders (rating subquery)
      rate_limit.py     # slowapi rate limiter setup
      recommendations.py  # Embedding-based recommendation engine
    db/models.py        # SQLModel database models (with pgvector columns)
    database.py         # DB initialization + pgvector setup
    entrypoint.sh       # Container startup script (runs DB init)
    tests/
      test_recommendations.py  # Recommendation engine unit tests
    Dockerfile          # Backend container
  frontend/             # React SPA (Vite + TypeScript + Tailwind v4)
    src/
      api/client.ts     # Axios HTTP client
      components/       # Reusable UI components (BookCard, SearchBar, RecommendationGrid, etc.)
      context/          # React contexts (AuthContext for JWT auth)
      hooks/            # TanStack React Query hooks (useBooks, useGenres, useRecommendations, etc.)
      pages/            # Route page components (BrowsePage, BookDetailPage, ProfilePage, etc.)
      types/            # TypeScript type definitions
      utils/            # Utility functions (slugify, validation)
    Dockerfile          # Frontend nginx container
  recommender/          # SVD collaborative filtering prototype (surprise)
  scraper/              # Scrapy project for bookmarks.reviews
  src/litmatch/         # Dagster ETL pipeline
    defs/
      assets/           # Dagster asset definitions (extract, transform, load, validate, embedding)
      resources/        # Dagster resources (database, path, scrapyd, embedding_model)
      schedules/        # Dagster schedules (weekly_etl_schedule)
      sensors/          # Dagster sensors (data freshness, startup ETL seed)
      utils/            # ETL utility functions (db_operations, transforms, validation)
  tests/
    dagster/            # Unit tests for Dagster assets, transforms, validation, sensors, embeddings
    integration/        # Integration tests (require running compose stack)
  compose.yaml          # Podman Compose services
  compose.test.yaml     # Override for integration tests
  Makefile              # Convenience targets
  pyproject.toml        # Python project config
  dagster.yaml          # Dagster instance config
  .env.example          # Environment variable template
```

## API Proxy Configuration

The frontend Vite dev server proxies `/api` requests to the backend:
- Frontend calls: `GET /api/books/`
- Proxy rewrites to: `GET http://localhost:8000/books/`

The `/api` prefix is **stripped** before forwarding. Backend routes have **no** `/api` prefix.

## REST API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/health` | Health check (database connectivity) | No |
| `POST` | `/auth/register` | Register new user | No |
| `POST` | `/auth/login` | Login (returns JWT) | No |
| `POST` | `/auth/refresh` | Refresh access token | Cookie |
| `POST` | `/auth/logout` | Logout (clears refresh cookie) | No |
| `GET` | `/books/` | List books (paginated, sortable) | No |
| `GET` | `/books/search` | Search books by title/author | No |
| `GET` | `/books/{book_id}` | Get book details | No |
| `GET` | `/reviews/{book_id}` | Get reviews for a book | No |
| `GET` | `/genres/` | List all genres | No |
| `GET` | `/users/me` | Get current user profile | Yes |
| `GET` | `/recommendations/` | Get personalized recommendations | Yes |
| `GET` | `/ratings/` | Get user's ratings | Yes |
| `POST` | `/ratings/` | Rate a book | Yes |

## Code Style

- **Python**: PEP 8, type annotations on all function signatures, format with black/ruff
- **TypeScript**: Strict mode, Tailwind CSS for styling
- **Immutability**: Prefer creating new objects over mutation
- **Error handling**: Handle errors explicitly; never silently swallow exceptions

## Database Schema

PostgreSQL with pgvector extension. Key entities defined in `backend/db/models.py`:
- **Book** — central entity (title, author, publisher, isbn, description, fiction flag, embedding vector)
- **Author**, **Publisher** — one-to-many with Book
- **Genre** — many-to-many with Book via BookGenreLink
- **Review** — linked to Book, Critic, and Publication (with embedding vector)
- **User**, **UserRating** — authentication and book ratings

Both `Book.embedding` and `Review.embedding` are 384-dimensional pgvector columns (`Vector(384)`) used by the recommendation engine.

## ETL Pipeline (Dagster)

### Asset Graph

```
crawl_books -> raw_books -> validate_raw_books -> cleaned_books -> load_books -> review_embeddings -> book_embeddings
                              \-> validation_errors
```

- **crawl_books**: Triggers Scrapyd spider and polls for completion (used by `crawl_and_load` job)
- **raw_books**: Reads and parses `books.jsonl` from scraper output
- **validate_raw_books**: Validates required fields, splits into valid records + error records
- **cleaned_books**: Transforms dates, ratings, fiction classification, critic names
- **load_books**: Upserts books, authors, publishers, genres, critics, publications, and reviews into PostgreSQL
- **review_embeddings**: Encodes review text into 384-dim vectors using sentence-transformers (incremental)
- **book_embeddings**: Averages review embeddings per book to produce book-level embeddings (incremental)

### Jobs

- **etl_pipeline**: Full ETL from raw_books through embeddings (no crawl)
- **crawl_and_load**: Crawl + full ETL including embeddings
- **embedding_pipeline**: Generate review and book embeddings only

### Schedules

- **weekly_etl_schedule**: Runs `crawl_and_load` every Sunday at midnight UTC (default: STOPPED, must be activated in Dagster UI)

### Sensors

- **data_freshness_sensor**: Ongoing file-watch, triggers ETL when `books.jsonl` is modified
- **startup_crawl_sensor**: Fires exactly once on first deployment when Scrapyd is healthy, triggers a full crawl-and-load pipeline to seed the database

## Recommendation Engine

The recommendation system uses embedding-based cosine similarity via pgvector:

1. **Review embeddings**: Generated by the `review_embeddings` Dagster asset using `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions)
2. **Book embeddings**: Computed as the mean of a book's review embeddings by the `book_embeddings` asset
3. **User taste embedding**: Computed at query time as a weighted average of rated book embeddings (weight = rating - 2, so 1-star is negative, 3+ is positive)
4. **Nearest-book search**: Uses pgvector `cosine_distance` to find books closest to the user's taste embedding
5. **Fallback**: Users with fewer than 5 ratings get popular books (by average critic rating) instead

Category filtering (`fiction`/`nonfiction`/`all`) is applied at every stage.

## Network Architecture

- **litnet** Podman network is used for inter-container communication when running via Makefile
- Compose services use the default compose network
- Backend health check endpoint (`/health`) verifies database connectivity with `SELECT 1`
