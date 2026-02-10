# LitMatch Runbook

## Service Overview

| Service | Port | Image / Runtime | Health Check |
|---------|------|-----------------|-------------|
| PostgreSQL (pgvector) | 5432 | `pgvector/pgvector:pg18` | `pg_isready -U bookuser -d bookdb` |
| FastAPI Backend | 8000 (compose) / 80 (Makefile) | Python 3.12 (Podman) | `GET /health` -> `{"status": "ok", "database": "connected"}` |
| Scrapyd | 6800 | Python Alpine (Podman) | `GET http://localhost:6800/` |
| Dagster Code Server | 4000 | Python 3.12 (Podman) | `dagster api grpc-health-check --port 4000` |
| Dagster Webserver | 3000 | Python 3.12 (Podman) | `GET http://localhost:3000/server_info` |
| Dagster Daemon | — | Python 3.12 (Podman) | `dagster-daemon liveness-check` |
| Frontend (nginx) | 8080 | nginx:alpine (Podman) | `GET http://localhost:8080/` |
| Vite Dev Server | 5173 | Local (`npm run dev`) | `GET http://localhost:5173` |

## Deployment

### Podman Compose (recommended for development)

```bash
# Start all services
make up
# or
podman compose up --build -d

# Verify services are running
podman compose ps

# Check logs
podman compose logs -f backend
podman compose logs -f db
make dagster-logs  # Dagster-specific logs
```

### Health Checks

All compose services have health checks. View status:

```bash
# Show service health status
podman compose ps

# Check individual service health
podman compose exec db pg_isready -U bookuser -d bookdb
curl http://localhost:8000/health
curl http://localhost:3000/server_info
wget --spider -q http://localhost:6800/
curl http://localhost:8080/
```

The backend `/health` endpoint verifies database connectivity by executing `SELECT 1`.
If the database is unreachable, the health check will fail and the service will be
marked as unhealthy.

**Startup ordering:**
- Backend waits for database to be healthy (`depends_on: condition: service_healthy`)
- Dagster daemon waits for both dagster-code and backend to be healthy (ensures DB schema is initialized before startup_crawl_sensor runs)
- Backend entrypoint script runs database initialization (table creation + pgvector extension) before launching the FastAPI server

### Standalone (Makefile targets)

```bash
# Creates a standalone PostgreSQL container on the litnet Podman network
make create-db

# Initialize schema (runs outside the container, connects to localhost:5432)
python -m backend.database

# Build and run API container on litnet network (exposes port 80)
make start-api

# Full standalone backend: DB + schema init + API
make start-backend

# Build and run frontend nginx container (exposes port 8080)
make start-frontend

# Start both backend and frontend
make start-all
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
# Local development
dg dev
# Opens at http://localhost:3000

# Via Podman Compose
make up
# or
podman compose up dagster-code dagster-webserver dagster-daemon -d
# Verify: curl http://localhost:3000/server_info
```

### Asset Graph

```
crawl_books -> raw_books -> validate_raw_books -> cleaned_books -> load_books -> review_embeddings -> book_embeddings
                              \-> validation_errors
```

- **crawl_books**: Triggers Scrapyd spider and polls for completion (used by `crawl_and_load` job)
- **raw_books**: Reads and parses `books.jsonl` from the scraper output volume
- **validate_raw_books**: Validates required fields, splits into valid records + error records
- **cleaned_books**: Transforms dates, ratings, fiction classification, critic names
- **load_books**: Upserts books, authors, publishers, genres, critics, publications, and reviews into PostgreSQL
- **review_embeddings**: Encodes review text into 384-dim dense vectors using sentence-transformers (incremental, skips rows that already have embeddings)
- **book_embeddings**: Averages review embeddings per book to produce book-level embeddings (incremental)

**Data source path** (configured in compose.yaml as volume mount):
```
Podman volume: litmatch_shared_scraper_output
Container path: /data/raw/books.jsonl
```

### Jobs

- **etl_pipeline**: Full ETL from raw_books through embeddings (no crawl)
- **crawl_and_load**: Crawl + full ETL including embeddings
- **embedding_pipeline**: Generate review and book embeddings only (useful for re-embedding without re-running ETL)

### Schedules

- **weekly_etl_schedule**: Runs `crawl_and_load` every Sunday at midnight UTC (default: STOPPED, must be activated in Dagster UI)

### Sensors

- **data_freshness_sensor**: Ongoing file-watch, triggers ETL when `books.jsonl` is modified
- **startup_crawl_sensor**: Fires exactly once on first deployment when Scrapyd is healthy, triggers a full crawl-and-load pipeline to seed the database

### Embedding Pipeline

The embedding assets run as part of the ETL pipeline (after `load_books`):

1. **review_embeddings**: Uses `sentence-transformers` (`all-MiniLM-L6-v2`) to encode review text into 384-dim vectors. Processes in batches of 256. Incremental: skips reviews that already have embeddings.
2. **book_embeddings**: Computes per-book embeddings by averaging all review embeddings for each book using numpy. Incremental: skips books that already have embeddings.

The embedding model is configured via the `EMBEDDING_MODEL_NAME` environment variable (default: `all-MiniLM-L6-v2`). Only allowlisted models are accepted to prevent arbitrary code execution from untrusted HuggingFace Hub models.

To re-generate embeddings without running the full ETL:
```bash
# Via Dagster UI: materialize the embedding_pipeline job
# Or trigger via GraphQL API
```

## Recommendation Engine

The `/recommendations/` API endpoint provides personalized book recommendations:

1. Computes a user taste embedding as a weighted average of rated book embeddings
2. Uses pgvector `cosine_distance` to find nearest books
3. Falls back to popular books (by average critic rating) for users with fewer than 5 ratings
4. Supports category filtering: `?category=fiction`, `?category=nonfiction`, or `?category=all`

## Scraper (Scrapy via Scrapyd)

### Running a spider

```bash
# With Scrapyd running (via compose or standalone)
make run-spider
# or
curl http://localhost:6800/schedule.json -d project=bookmarks -d spider=bookmarks
```

### Checking spider status

```bash
curl http://localhost:6800/listjobs.json?project=bookmarks
```

Output is written to the `shared_scraper_output` Podman volume as `books.jsonl`.

### Scraper Configuration

- **Target**: bookmarks.reviews (sitemap spider)
- **Middleware**: Rotating proxies, user-agent rotation
- **Output format**: JSONL (one JSON object per line)
- **Proxy token**: Set `PROXY_TOKEN` in `.env`

## Common Issues and Fixes

### Database connection refused

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Fix**:
1. Verify the database container is running: `podman compose ps db`
2. Check that port 5432 is not in use: `lsof -i :5432`
3. Verify `.env` has correct `DATABASE_URL`
4. If using Makefile targets, ensure the `litnet` Podman network exists: `podman network create litnet`
5. Check database logs: `podman compose logs db`

### pgvector extension not found

**Symptom**: `ERROR: could not open extension control file "/usr/share/postgresql/.../vector.control"`

**Fix**: Ensure you're using the `pgvector/pgvector:pg18` image, not a plain `postgres` image. The Makefile `create-db` target uses plain `postgres`; prefer `podman compose up db -d` instead.

### Frontend API requests return 404

**Symptom**: `/api/books/` returns 404 in the browser

**Fix**:
1. Ensure the backend is running on port 8000: `curl http://localhost:8000/health`
2. Verify the Vite proxy is configured in `frontend/vite.config.ts`
3. The proxy strips `/api` prefix: frontend `GET /api/books/` becomes backend `GET /books/`
4. Check that the backend is actually serving routes (visit `http://localhost:8000/docs`)
5. Check CORS configuration in `.env` (`CORS_ORIGINS` should include `http://localhost:5173`)

### Dagster can't find books.jsonl

**Symptom**: `Raw data path does not exist` error in Dagster logs or asset materialization UI

**Fix**:
1. Run the scraper first to generate `books.jsonl`: `make run-spider`
2. Check the Podman volume: `podman volume inspect litmatch_shared_scraper_output`
3. Verify the volume mount in `compose.yaml` (should mount to `/data/raw` in dagster containers)
4. Manually inspect volume contents:
   ```bash
   podman run --rm -v litmatch_shared_scraper_output:/data alpine ls -la /data/raw
   ```

### Dagster startup_crawl_sensor not triggering

**Symptom**: Database is empty after first deployment

**Fix**:
1. Check dagster-daemon logs: `make dagster-logs` or `podman compose logs dagster-daemon`
2. Verify the scrapyd service is healthy: `podman compose ps scrapyd`
3. Verify the backend service is healthy: `podman compose ps backend`
4. Ensure dagster-daemon depends on both `dagster-code` and `backend` in `compose.yaml`
5. Check that database initialization completed: `podman compose logs backend | grep "Database initialized"`
6. Manually trigger crawl_and_load job from Dagster UI: http://localhost:3000

### Port conflict between Makefile and Podman Compose

**Symptom**: `Bind for 0.0.0.0:5432 failed: port is already allocated`

**Fix**: Don't mix Makefile targets and Podman Compose. Use one or the other:
- **Compose**: `make up` or `podman compose up --build -d` (ports: 5432, 8000, 6800, 3000, 4000, 8080)
- **Makefile**: `make start-backend` (ports: 5432, 80)

Stop the conflicting service first:
```bash
make down
# or
podman stop db backend dagster-code dagster-webserver dagster-daemon
```

### Large etl.log file

A ~200MB `etl.log` may exist in the project root (gitignored via `*.log`). Safe to delete:
```bash
rm -f etl.log
```

### Backend health check failing

**Symptom**: Backend container is running but health check fails, shows "unhealthy" in `podman compose ps`

**Fix**:
1. Check backend logs: `podman compose logs backend`
2. Test health endpoint manually: `curl http://localhost:8000/health`
3. Verify database connectivity from backend container:
   ```bash
   podman compose exec backend psql $DATABASE_URL -c "SELECT 1"
   ```
4. Check that `DATABASE_URL` in `.env` is correct (use `db` as hostname for compose)
5. Verify pgvector extension is installed: `podman compose exec db psql -U bookuser -d bookdb -c "SELECT * FROM pg_extension WHERE extname = 'vector'"`

### Embedding generation fails

**Symptom**: `review_embeddings` or `book_embeddings` asset materialization fails in Dagster

**Fix**:
1. Check Dagster run logs for the specific error message
2. Verify `sentence-transformers` and `torch` are installed: `uv run python -c "from sentence_transformers import SentenceTransformer; print('OK')"`
3. Ensure `EMBEDDING_MODEL_NAME` is in the allowlist (`all-MiniLM-L6-v2`)
4. Check available memory — the model requires ~100MB RAM
5. Both assets have `retry_policy` with 1 retry and 60s delay; check if the retry also failed
6. To re-run embeddings only: materialize the `embedding_pipeline` job in Dagster UI

### Recommendations returning empty or popular-only results

**Symptom**: `/recommendations/` endpoint returns popular books instead of personalized ones

**Fix**:
1. User needs at least 5 ratings for personalized recommendations (fewer falls back to popular)
2. Verify book embeddings exist: `podman compose exec db psql -U bookuser -d bookdb -c "SELECT count(*) FROM book WHERE embedding IS NOT NULL;"`
3. If no embeddings, run the embedding pipeline in Dagster UI
4. Check that rated books have embeddings — books without review text won't have embeddings

## Rollback Procedures

### Backend rollback

```bash
# Stop the current backend
podman compose stop backend

# Rebuild from a specific commit
git checkout <commit-hash> -- backend/
podman compose up --build -d backend
```

### Frontend rollback

```bash
# Stop the current frontend
podman compose stop frontend

# Rebuild from a specific commit
git checkout <commit-hash> -- frontend/
podman compose up --build -d frontend
```

### Dagster rollback

```bash
# Stop Dagster services
podman compose stop dagster-code dagster-webserver dagster-daemon

# Rebuild from a specific commit
git checkout <commit-hash> -- src/litmatch/
podman compose up --build -d dagster-code dagster-webserver dagster-daemon
```

### Database rollback

There is no migration framework (e.g., Alembic) currently. Schema changes require:
1. Drop and recreate tables (data loss): `python -m backend.database`
2. Or restore from a PostgreSQL backup

### Creating a database backup

```bash
# Backup all data
podman compose exec db pg_dump -U bookuser bookdb > backup_$(date +%Y%m%d).sql

# Backup schema only
podman compose exec db pg_dump -U bookuser bookdb --schema-only > schema_$(date +%Y%m%d).sql

# Backup specific tables
podman compose exec db pg_dump -U bookuser bookdb -t book -t author > books_authors_$(date +%Y%m%d).sql
```

### Restoring from backup

```bash
# Full restore (will fail if tables already exist)
podman compose exec -T db psql -U bookuser bookdb < backup_YYYYMMDD.sql

# Drop and recreate database, then restore
podman compose exec db dropdb -U bookuser bookdb
podman compose exec db createdb -U bookuser bookdb
podman compose exec -T db psql -U bookuser bookdb < backup_YYYYMMDD.sql
```

## Monitoring

### Container health

```bash
# Check all service health status
podman compose ps

# Follow logs for all services
make logs

# Follow backend logs only
podman compose logs --tail=50 -f backend

# Follow Dagster logs
make dagster-logs

# Check resource usage
podman stats
```

### Database status

```bash
# Check database is ready
podman compose exec db pg_isready -U bookuser -d bookdb

# Count books in database
podman compose exec db psql -U bookuser -d bookdb -c "SELECT count(*) FROM book;"

# Check embedding coverage
podman compose exec db psql -U bookuser -d bookdb -c "SELECT count(*) AS total_books, count(embedding) AS with_embeddings FROM book;"
podman compose exec db psql -U bookuser -d bookdb -c "SELECT count(*) AS total_reviews, count(embedding) AS with_embeddings FROM review;"

# Check database connections
podman compose exec db psql -U bookuser -d bookdb -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'bookdb';"

# Check table sizes
podman compose exec db psql -U bookuser -d bookdb -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

### Backend API status

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs

# Test authentication
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "email": "test@example.com", "password": "testpass123"}'

# Test book search
curl "http://localhost:8000/books/?limit=5"

# Test recommendations (requires auth token)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "testpass123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/recommendations/?category=all"
```

### Dagster status

Check the Dagster UI at http://localhost:3000 for:
- Asset materialization history
- Run logs and error details
- Pipeline scheduling status
- Sensor status (data_freshness_sensor, startup_crawl_sensor)
- Embedding pipeline progress (review_embeddings, book_embeddings)

```bash
# Check if Dagster webserver is responding
curl http://localhost:3000/server_info

# Check if code server is responding
nc -z localhost 4000 && echo "Code server is up" || echo "Code server is down"
```

### Scraper status

```bash
# Check Scrapyd is running
curl http://localhost:6800/

# List all jobs
curl http://localhost:6800/listjobs.json?project=bookmarks

# Check scraper output
podman run --rm -v litmatch_shared_scraper_output:/data alpine cat /data/raw/books.jsonl | wc -l
```

## Performance Tuning

### Database

```bash
# Analyze query performance
podman compose exec db psql -U bookuser -d bookdb -c "EXPLAIN ANALYZE SELECT * FROM book WHERE title ILIKE '%gatsby%';"

# Check slow queries (requires pg_stat_statements extension)
podman compose exec db psql -U bookuser -d bookdb -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Vacuum and analyze tables
podman compose exec db psql -U bookuser -d bookdb -c "VACUUM ANALYZE;"
```

### Backend

- Rate limiting is enabled via `slowapi` (configured in `backend/app/rate_limit.py`)
- CORS is configured in `.env` via `CORS_ORIGINS`
- Consider adding a Redis cache for frequently accessed data

### Dagster

- Asset materialization history is stored in the Dagster instance database
- Consider increasing parallel asset execution in `dagster.yaml`
- Monitor run queue length in Dagster UI
- Embedding assets have retry policies (1 retry, 60s delay) for transient failures

## Environment Variables Reference

See `.env.example` for all available environment variables.

**Required variables:**
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `SECRET_KEY`

**Optional variables:**
- `CORS_ORIGINS` (default: `http://localhost:5173,http://localhost:8080`)
- `COOKIE_SECURE` (default: `false`)
- `REFRESH_COOKIE_PATH` (default: `/api/auth/refresh`)
- `PROXY_TOKEN` (required only for scraping)
- `RAW_DATA_DIR` (set automatically in compose.yaml)
- `EMBEDDING_MODEL_NAME` (default: `all-MiniLM-L6-v2`)

## Troubleshooting Checklist

When services fail to start, check in this order:

1. **Environment variables**: `cat .env` — ensure all required vars are set
2. **Database**: `podman compose ps db` — must be healthy before backend starts
3. **Backend**: `curl http://localhost:8000/health` — must return `{"status": "ok"}`
4. **Dagster**: `curl http://localhost:3000/server_info` — webserver must be running
5. **Volumes**: `podman volume ls` — ensure volumes exist
6. **Networks**: `podman network ls` — ensure `litnet` exists (for Makefile targets)
7. **Ports**: `lsof -i :5432 -i :8000 -i :3000` — check for port conflicts
8. **Logs**: `make logs` — check for error messages
