# LitMatch Runbook

## Service Overview

| Service | Port | Image / Runtime | Health Check |
|---------|------|-----------------|-------------|
| PostgreSQL (pgvector) | 5432 | `pgvector/pgvector:pg18` | `pg_isready -U bookuser -d bookdb` |
| FastAPI Backend | 8000 (compose) / 80 (Makefile) | Python 3.12 (Podman) | `GET /health` → `{"status": "ok"}` |
| Scrapyd | 6800 | Python Alpine (Podman) | `GET http://localhost:6800/` |
| Dagster UI | 3000 | Local (`dg dev`) | `GET http://localhost:3000` |
| Vite Dev Server | 5173 | Local (`npm run dev`) | `GET http://localhost:5173` |

## Deployment

### Podman Compose (recommended for development)

```bash
# Start all services
podman compose up --build -d

# Verify services are running
podman compose ps

# Check logs
podman compose logs -f backend
podman compose logs -f db
```

### Health Checks

All compose services have health checks. View status:

```bash
# Show service health status
podman compose ps

# Check individual service health
podman compose exec db pg_isready -U bookuser -d bookdb
curl http://localhost:8000/health
wget --spider -q http://localhost:6800/
```

The backend `/health` endpoint verifies database connectivity by executing `SELECT 1`.
If the database is unreachable, the health check will fail and the service will be
marked as unhealthy.

**Startup ordering:** The backend service waits for the database to be healthy
(`depends_on: condition: service_healthy`) before starting. The entrypoint script
runs database initialization (table creation + pgvector extension) before launching
the FastAPI server.

### Standalone (Makefile targets)

```bash
# Creates a standalone PostgreSQL container on the litnet Podman network
make create-db

# Initialize schema (runs outside the container, connects to localhost:5432)
python -m backend.database

# Build and run API container on litnet network (exposes port 80)
make start-api
```

**Port note**: `make start-api` exposes port **80**, while `podman compose` exposes port **8000**. Use compose for development.

### Database Initialization

The schema is created by `backend/database.py`, which:
1. Enables the `vector` extension (pgvector)
2. Creates all tables via `SQLModel.metadata.create_all()`

Run manually:
```bash
python -m backend.database
```

Or it runs automatically at container startup via `backend/entrypoint.sh`, which
executes `python -m backend.database` before starting the FastAPI server.

## ETL Pipeline (Dagster)

### Starting Dagster

```bash
dg dev
# Opens at http://localhost:3000
```

### Asset Graph

```
raw_books → validate_raw_books → cleaned_books → load_books
              ↘ validation_errors
```

- **raw_books**: Reads and parses `books.jsonl` from the scraper output volume
- **validate_raw_books**: Validates required fields, splits into valid records + error records
- **cleaned_books**: Transforms dates, ratings, fiction classification, critic names
- **load_books**: Upserts books, authors, publishers, genres, critics, publications, and reviews into PostgreSQL

**Data source path** (configured in `src/litmatch/defs/assets.py`):
```
/home/framework/.local/share/containers/storage/volumes/litmatch_shared_scraper_output/_data/raw/books.jsonl
```

### Legacy Assets

`assets_legacy.py` contains the original monolithic asset definitions (`raw_data`, `cleaned_data`, `load_to_db`). These are disconnected from the active pipeline which uses the modular assets in `defs/assets/`.

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

Output is written to the `shared_scraper_output` Podman volume as `books.jsonl`.

## Common Issues and Fixes

### Database connection refused

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Fix**:
1. Verify the database container is running: `podman compose ps db`
2. Check that port 5432 is not in use: `lsof -i :5432`
3. Verify `.env` has correct `DATABASE_URL`
4. If using Makefile targets, ensure the `litnet` Podman network exists: `podman network create litnet`

### pgvector extension not found

**Symptom**: `ERROR: could not open extension control file "/usr/share/postgresql/.../vector.control"`

**Fix**: Ensure you're using the `pgvector/pgvector:pg18` image, not a plain `postgres` image. The Makefile `create-db` target uses plain `postgres`; prefer `podman compose up db -d` instead.

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
3. Check the Podman volume: `podman volume inspect litmatch_shared_scraper_output`

### Port conflict between Makefile and Podman Compose

**Symptom**: `Bind for 0.0.0.0:5432 failed: port is already allocated`

**Fix**: Don't mix Makefile targets and Podman Compose. Use one or the other:
- **Compose**: `podman compose up --build -d` (ports: 5432, 8000, 6800)
- **Makefile**: `make start-backend` (ports: 5432, 80)

Stop the conflicting service first: `podman compose down` or `podman stop db backend`

### Large etl.log file

A ~200MB `etl.log` may exist in the project root (gitignored via `*.log`). Safe to delete:
```bash
rm -f etl.log
```

## Rollback Procedures

### Backend rollback

```bash
# Stop the current backend
podman compose stop backend

# Rebuild from a specific commit
git checkout <commit-hash> -- backend/
podman compose up --build -d backend
```

### Database rollback

There is no migration framework (e.g., Alembic) currently. Schema changes require:
1. Drop and recreate tables (data loss): `python -m backend.database`
2. Or restore from a PostgreSQL backup

### Creating a database backup

```bash
podman compose exec db pg_dump -U bookuser bookdb > backup_$(date +%Y%m%d).sql
```

### Restoring from backup

```bash
podman compose exec -T db psql -U bookuser bookdb < backup_YYYYMMDD.sql
```

## Monitoring

### Container health

```bash
podman compose ps
podman compose logs --tail=50 backend
podman compose logs --tail=50 db
```

### Database status

```bash
podman compose exec db pg_isready -U bookuser -d bookdb
podman compose exec db psql -U bookuser -d bookdb -c "SELECT count(*) FROM book;"
```

### Dagster run status

Check the Dagster UI at http://localhost:3000 for:
- Asset materialization history
- Run logs and error details
- Pipeline scheduling status
