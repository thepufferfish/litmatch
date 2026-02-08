# LitMatch Runbook

## Service Overview

| Service | Port | Image / Runtime | Health Check |
|---------|------|-----------------|-------------|
| PostgreSQL (pgvector) | 5432 | `pgvector/pgvector:pg18` | `pg_isready -U bookuser -d bookdb` |
| FastAPI Backend | 8000 | Python 3.12 (Docker) | `GET /docs` (Swagger UI) |
| Scrapyd | 6800 | Python Alpine (Docker) | `GET http://localhost:6800/` |
| Dagster UI | 3000 | Local (`dg dev`) | `GET http://localhost:3000` |
| Vite Dev Server | 5173 | Local (`npm run dev`) | `GET http://localhost:5173` |

## Deployment

### Docker Compose (recommended for development)

```bash
# Start all services
docker compose up --build -d

# Verify services are running
docker compose ps

# Check logs
docker compose logs -f backend
docker compose logs -f db
```

### Standalone (Makefile targets)

```bash
# Creates a standalone PostgreSQL container on the litnet Docker network
make create-db

# Initialize schema (runs outside Docker, connects to localhost:5432)
python -m backend.database

# Build and run API container on litnet network (exposes port 80)
make start-api
```

**Port note**: `make start-api` exposes port **80**, while `docker compose` exposes port **8000**. Use compose for development.

### Database Initialization

The schema is created by `backend/database.py`, which:
1. Enables the `vector` extension (pgvector)
2. Creates all tables via `SQLModel.metadata.create_all()`

Run manually:
```bash
python -m backend.database
```

Or it runs automatically during the Docker backend build (`RUN python -m backend.database` in `backend/Dockerfile`).

## ETL Pipeline (Dagster)

### Starting Dagster

```bash
dg dev
# Opens at http://localhost:3000
```

### Asset Graph

```
extract (load books.jsonl) -> load_to_db (upsert to PostgreSQL)
```

- **extract**: Reads `books.jsonl` from the scraper output volume
- **load_to_db**: Upserts books, authors, publishers, genres, critics, publications, and reviews

**Data source path** (configured in `src/litmatch/defs/assets.py`):
```
/home/framework/.local/share/containers/storage/volumes/litmatch_shared_scraper_output/_data/raw/books.jsonl
```

### Orphaned Assets

`raw_data` and `cleaned_data` assets (plus `fix_publish_dates`, `check_if_fiction`, `add_fiction_flag` helpers) are disconnected from the active pipeline. They exist for potential future use.

## Scraper (Scrapy via Scrapyd)

### Running a spider

```bash
# With Scrapyd running (via compose or standalone)
curl http://localhost:6800/schedule.json -d project=bookmarks -d spider=bookmarks
```

### Checking spider status

```bash
curl http://localhost:6800/listjobs.json?project=bookmarks
```

Output is written to the `shared_scraper_output` Docker volume as `books.jsonl`.

## Common Issues and Fixes

### Database connection refused

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Fix**:
1. Verify the database container is running: `docker compose ps db`
2. Check that port 5432 is not in use: `lsof -i :5432`
3. Verify `.env` has correct `DATABASE_URL`
4. If using Makefile targets, ensure the `litnet` Docker network exists: `docker network create litnet`

### pgvector extension not found

**Symptom**: `ERROR: could not open extension control file "/usr/share/postgresql/.../vector.control"`

**Fix**: Ensure you're using the `pgvector/pgvector:pg18` image, not a plain `postgres` image. The Makefile `create-db` target uses plain `postgres`; prefer `docker compose up db -d` instead.

### Frontend API requests return 404

**Symptom**: `/api/books/` returns 404 in the browser

**Fix**:
1. Ensure the backend is running on port 8000
2. Verify the Vite proxy is configured in `frontend/vite.config.ts`
3. The proxy strips `/api` prefix: frontend `GET /api/books/` becomes backend `GET /books/`
4. Check that the backend is actually serving routes (visit `http://localhost:8000/docs`)

### Dagster can't find books.jsonl

**Symptom**: `Raw data path does not exist` error in Dagster logs

**Fix**:
1. Run the scraper first to generate `books.jsonl`
2. Verify the `RAW_DATA_DIR` path in `src/litmatch/defs/assets.py` matches your local volume mount
3. Check the Docker volume: `docker volume inspect litmatch_shared_scraper_output`

### Port conflict between Makefile and Docker Compose

**Symptom**: `Bind for 0.0.0.0:5432 failed: port is already allocated`

**Fix**: Don't mix Makefile targets and Docker Compose. Use one or the other:
- **Compose**: `docker compose up --build -d` (ports: 5432, 8000, 6800)
- **Makefile**: `make start-backend` (ports: 5432, 80)

Stop the conflicting service first: `docker compose down` or `docker stop db backend`

### Large etl.log file

A ~200MB `etl.log` may exist in the project root (gitignored via `*.log`). Safe to delete:
```bash
rm -f etl.log
```

## Rollback Procedures

### Backend rollback

```bash
# Stop the current backend
docker compose stop backend

# Rebuild from a specific commit
git checkout <commit-hash> -- backend/
docker compose up --build -d backend
```

### Database rollback

There is no migration framework (e.g., Alembic) currently. Schema changes require:
1. Drop and recreate tables (data loss): `python -m backend.database`
2. Or restore from a PostgreSQL backup

### Creating a database backup

```bash
docker compose exec db pg_dump -U bookuser bookdb > backup_$(date +%Y%m%d).sql
```

### Restoring from backup

```bash
docker compose exec -T db psql -U bookuser bookdb < backup_YYYYMMDD.sql
```

## Monitoring

### Container health

```bash
docker compose ps
docker compose logs --tail=50 backend
docker compose logs --tail=50 db
```

### Database status

```bash
docker compose exec db pg_isready -U bookuser -d bookdb
docker compose exec db psql -U bookuser -d bookdb -c "SELECT count(*) FROM book;"
```

### Dagster run status

Check the Dagster UI at http://localhost:3000 for:
- Asset materialization history
- Run logs and error details
- Pipeline scheduling status
