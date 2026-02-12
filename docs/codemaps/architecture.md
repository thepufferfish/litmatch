# Architecture Codemap

> Freshness: 2026-02-08 | Auto-generated from source analysis

## System Diagram

```
                    bookmarks.reviews
                          |
                    Scrapy Spider
                    (sitemap-based)
                          |
               raw_books_staging table
                    (PostgreSQL)
                          |
             Dagster ETL (multi-stage pipeline)
             raw_books → validate → transform → load → embeddings
                          |
                    PostgreSQL + pgvector
                          |
                  FastAPI REST API (port 8000)
                   /auth  /books  /reviews
                   /genres /ratings /recommendations
                          |
                  React SPA (port 5173)
                  Vite + TS + Tailwind v4
```

## Component Map

| Component | Directory | Runtime | Port |
|-----------|-----------|---------|------|
| Scraper | `scraper/` | Scrapyd (Podman) | 6800 |
| ETL Pipeline | `src/litmatch/` | Dagster | 3000 |
| Database | — | pgvector/pgvector:pg18 | 5432 |
| Backend API | `backend/` | FastAPI (Podman) | 8000 |
| Frontend | `frontend/` | Vite dev server | 5173 |
| Recommender | `recommender/` | Script (offline) | — |

## Data Flow

```
1. Spider crawls bookmarks.reviews sitemap
2. Writes scraped items to raw_books_staging table in PostgreSQL
3. Dagster reads staging table → validates → transforms → upserts to PostgreSQL → generates embeddings
4. FastAPI serves paginated books, reviews, genres, ratings, recommendations
5. React SPA fetches via /api proxy → renders browse/detail/auth/profile pages
6. Users rate books → stored in PostgreSQL → powers embedding-based recommendations
```

## Inter-Component Dependencies

```
scraper → raw_books_staging table (PostgreSQL write)
dagster  → raw_books_staging (read) + PostgreSQL (write) + backend.db.models (import)
backend  → PostgreSQL (read/write) + .env (config)
frontend → backend /api proxy (HTTP)
recommender → reviews.csv (offline, superseded by embedding approach)
```

## Authentication Flow

```
Register/Login → JWT access token (15 min) + httpOnly refresh cookie (7 days)
API requests   → Bearer token in Authorization header
401 response   → Auto-refresh via cookie → retry original request
Logout         → Revoke refresh token + clear cookie
```

## Configuration Sources

| Source | Used By | Key Vars |
|--------|---------|----------|
| `.env` | compose, Makefile, backend | DATABASE_URL, SECRET_KEY, CORS_ORIGINS |
| `pyproject.toml` | uv, hatch, dagster dg | Python deps, build config |
| `compose.yaml` | Podman Compose | Service definitions, volumes, ports |
| `Makefile` | Dev scripts | Standalone container targets |
| `dagster.yaml` | Dagster | Instance logging config |
| `frontend/package.json` | npm, Vite | JS deps, scripts |
| `frontend/vite.config.ts` | Vite | Proxy, aliases, test config |
