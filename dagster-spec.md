# dagster-spec.md -- Dagster Pipeline Specification for LitMatch

## 1. Overview and Goals

### Purpose

This document specifies the architecture, implementation plan, and phased roadmap for rebuilding the LitMatch data pipeline on Dagster. The pipeline ingests book and review data from the bookmarks.reviews scraper, transforms and validates it, loads it into PostgreSQL with pgvector, and (in later phases) generates embeddings for semantic search and trains a recommendation model.

### Goals

1. **Reliability** -- Replace the monolithic, fragile ETL with a modular asset graph that handles errors gracefully and quarantines bad data instead of failing entire runs.
2. **Observability** -- Every stage of the pipeline produces metadata visible in the Dagster UI: record counts, validation pass/fail rates, load durations, quarantine summaries.
3. **Orchestration** -- Dagster manages the full lifecycle: triggering the scraper, transforming data, loading to the database, and generating embeddings. Weekly automated runs.
4. **Deployability** -- The pipeline runs as Podman Compose services (webserver + daemon) alongside the existing database, backend, and scraper containers.
5. **Testability** -- Unit tests for transformation functions and integration tests for the full asset graph against a test database.

### Non-Goals (Current Scope)

- CI/CD integration (future)
- External monitoring or alerting (Dagster UI + Podman logs suffice)
- Recommender model training as a Dagster asset (Phase 4, long-term)
- Migration to cloud object storage (MinIO/S3) for raw data (future, when needed)

---

## 2. Current State Assessment

### What Exists

| Component | State | Notes |
|-----------|-------|-------|
| Scraper (Scrapy + Scrapyd) | **Working** | Containerized, triggered via `curl` to Scrapyd API. Outputs `books.jsonl` to a Podman volume. Supports incremental scraping via sitemap `lastmod` metadata. |
| `extract` asset | **Likely functional** | Reads `books.jsonl` from a hardcoded container volume path. Returns `list[dict]`. |
| `load_to_db` asset | **Unknown** | Monolithic function: iterates all records, does get-or-create for 6 entity types, upserts books, deduplicates reviews. No error handling for bad records. |
| `raw_data` asset | **Orphaned** | Reads same JSONL into a Pandas DataFrame. Not connected to `load_to_db`. |
| `cleaned_data` asset | **Orphaned** | Depends on `raw_data`. Fixes dates and adds fiction flag. Not connected to `load_to_db`. |
| `fix_publish_date` (function) | **Duplicated** | Exists as both a DataFrame-level function (`fix_publish_dates`) and a single-record function (`fix_publish_date`). The single-record version is used by `load_to_db`. |
| Database models | **Working** | SQLModel models for Book, Author, Publisher, Genre, Review, Critic, Publication, User, UserRating. pgvector extension created but no embedding columns. |
| Recommender | **Standalone** | Reads from `reviews.csv` (manual export), trains SVD model, prints results. No Dagster integration. |
| Dagster config | **Minimal** | `dagster.yaml` only configures SQLAlchemy log forwarding. No resources, IO managers, schedules, or sensors defined. `resources.py` is empty. |

### Data Volume

- Approximately 13,000 books with associated reviews, authors, publishers, genres, critics, and publications.
- Raw data file (`books.jsonl`) is manageable in size (single-digit megabytes).
- Weekly refresh cadence means low throughput requirements.

### Technical Debt

1. **Hardcoded paths**: `RAW_DATA_DIR` points to a specific Podman volume path (`/home/framework/.local/share/containers/storage/volumes/...`).
2. **Module-level engine**: `engine = create_engine(DATABASE_URL, echo=True)` created at import time, not as a Dagster resource.
3. **No error isolation**: A single bad record (e.g., unknown rating string) raises `ValueError` and fails the entire materialization.
4. **Duplicated logic**: Date fixing exists in two forms. Fiction classification logic exists but is not used by the active pipeline.
5. **No validation**: Raw scraper output is trusted without schema validation.
6. **Typing issues**: Uses `typing.List` and `typing.Dict` instead of built-in `list` and `dict`.
7. **Mutable patterns**: `prepare_book` mutates existing Book objects in-place rather than creating new instances.

---

## 3. Architecture Design

### 3.1 Asset Graph

The pipeline is organized into five stages, each a separate Dagster asset. An additional asset captures quarantined records.

```
                  +-----------------+
                  | trigger_scrape  |  (op within a job, not an asset)
                  +--------+--------+
                           |
                           v
                  +-----------------+
                  |   raw_books     |  Reads books.jsonl, returns list[dict]
                  +--------+--------+
                           |
                  +--------+--------+
                  |                 |
                  v                 v
        +------------------+  +---------------------+
        | validated_books  |  | quarantined_records  |
        +--------+---------+  +----------------------+
                 |
                 v
        +------------------+
        |  cleaned_books   |  Date fixing, normalization
        +--------+---------+
                 |
                 v
        +------------------+
        |   load_books     |  Upsert to PostgreSQL
        +------------------+
                 |
                 v  (Phase 3)
        +------------------+
        |  book_embeddings |  Generate & store vectors
        +------------------+
```

#### Asset Descriptions

| Asset | Input | Output | Description |
|-------|-------|--------|-------------|
| `raw_books` | filesystem (books.jsonl) | `list[dict]` | Reads the JSONL file line by line. Logs parse errors but does not fail on individual bad lines. Emits metadata: `total_lines`, `parse_errors`. |
| `validated_books` | `raw_books` | `list[dict]` | Validates each record against a schema (required fields, types, review structure). Valid records pass through. Invalid records are routed to `quarantined_records`. Emits metadata: `valid_count`, `quarantined_count`, `error_summary` (counts by error type). |
| `quarantined_records` | (produced by `validated_books`) | `list[dict]` | Each quarantined record includes the original data plus an `errors` field listing all validation failures. Written to a JSONL file for inspection. This is a **multi-asset** output from the validation step. |
| `cleaned_books` | `validated_books` | `list[dict]` | Applies transformations: fix publish dates, normalize author/publisher names (strip whitespace, fix encoding), encode review ratings (string to int). Emits metadata: `date_fixes_applied`, `records_processed`. |
| `load_books` | `cleaned_books` | `None` (materializes to DB) | Upserts books and all related entities (Author, Publisher, Genre, Review, Critic, Publication) into PostgreSQL. Uses batch operations where possible. Emits metadata: `books_created`, `books_updated`, `books_skipped` (same or older scrape date). |
| `book_embeddings` (Phase 3) | `load_books` (dependency) | `None` (materializes to DB) | Reads books from DB that lack embeddings, generates vectors using a local sentence-transformers model, stores in pgvector column. Emits metadata: `embeddings_generated`, `model_name`, `dimensions`. |

#### Multi-Asset for Validation

The `validated_books` and `quarantined_records` assets are produced together using `@multi_asset`:

```python
@dg.multi_asset(
    outs={
        "validated_books": dg.AssetOut(description="Records that passed validation"),
        "quarantined_records": dg.AssetOut(description="Records that failed validation"),
    }
)
def validate_books(context: dg.AssetExecutionContext, raw_books: list[dict]) -> tuple:
    valid = []
    quarantined = []
    for record in raw_books:
        errors = validate_record(record)
        if errors:
            quarantined.append({**record, "validation_errors": errors})
        else:
            valid.append(record)
    # ... emit metadata, return both
```

### 3.2 Resources

| Resource | Type | Purpose |
|----------|------|---------|
| `database` | `DatabaseResource` (custom) | Wraps SQLModel engine creation. Configured via `DATABASE_URL` env var. Provides `get_session()` context manager. Replaces module-level `engine`. |
| `scraper_api` | `ScrapydResource` (custom) | HTTP client for the Scrapyd API. Configured with `scrapyd_url` (default: `http://scrapyd:6800`). Methods: `schedule_crawl()`, `poll_job_status()`, `is_job_finished()`. |
| `raw_data_dir` | `PathResource` (custom) | Configurable filesystem path for raw data I/O. Default: `/data/raw`. Replaces hardcoded `RAW_DATA_DIR`. |
| `embedding_model` | `EmbeddingModelResource` (Phase 3) | Loads and caches a sentence-transformers model. Configured with `model_name` (default: `all-MiniLM-L6-v2`). Provides `encode(texts: list[str]) -> list[list[float]]`. |

#### Resource Configuration

Resources are configured in `definitions.py` and read from environment variables:

```python
resources={
    "database": DatabaseResource(
        database_url=dg.EnvVar("DATABASE_URL"),
    ),
    "scraper_api": ScrapydResource(
        scrapyd_url=dg.EnvVar("SCRAPYD_URL"),
    ),
    "raw_data_dir": PathResource(
        path=dg.EnvVar("RAW_DATA_DIR"),
    ),
}
```

### 3.3 IO Strategy

No custom IO managers for Phase 1. Assets pass Python objects (lists of dicts) directly between steps via Dagster's default in-memory/pickle IO manager. This is appropriate because:

- The dataset (13K books) fits comfortably in memory.
- The pipeline runs on a single machine.
- Inter-asset data does not need to be persisted independently (the database is the durable store).

The `quarantined_records` asset writes its output to a JSONL file in the `raw_data_dir` path for manual inspection. This is handled within the asset code, not via an IO manager.

If the dataset grows significantly or multi-machine execution becomes necessary, migrate to a `FilesystemIOManager` or `S3IOManager` (with MinIO).

### 3.4 Schedule

A single weekly schedule triggers the full pipeline:

```python
@dg.schedule(
    cron_schedule="0 3 * * 0",  # 3:00 AM UTC every Sunday
    target=dg.AssetSelection.all(),
    default_status=dg.DefaultScheduleStatus.RUNNING,
)
def weekly_etl_schedule():
    ...
```

The schedule targets all assets. Dagster's dependency resolution ensures they execute in the correct order: `trigger_scrape` (job) -> `raw_books` -> `validated_books` / `quarantined_records` -> `cleaned_books` -> `load_books`.

### 3.5 Scraper Job

The scraper is triggered via a Dagster **job** (not an asset, because the scraper itself is not a data artifact -- it is a side-effectful process that produces a file). The job contains a single op:

```python
@dg.op
def trigger_scrape(context: dg.OpExecutionContext, scraper_api: ScrapydResource):
    job_id = scraper_api.schedule_crawl(project="bookmarks", spider="bookmarks")
    context.log.info(f"Scrapyd job started: {job_id}")

    while not scraper_api.is_job_finished(job_id):
        time.sleep(30)
        context.log.debug(f"Waiting for scrape job {job_id}...")

    context.log.info(f"Scrape job {job_id} completed")
```

The `raw_books` asset depends on successful completion of this job. This is modeled using `deps` on the asset or by making the schedule run the job first, then materialize assets.

### 3.6 Sensor (Alternative to Schedule)

As an alternative or complement to the weekly schedule, a **file sensor** can detect when `books.jsonl` has been modified and trigger the downstream assets automatically:

```python
@dg.sensor(
    asset_selection=dg.AssetSelection.keys("raw_books"),
    minimum_interval_seconds=3600,
)
def new_scrape_data_sensor(context: dg.SensorEvaluationContext, raw_data_dir: PathResource):
    jsonl_path = os.path.join(raw_data_dir.path, "books.jsonl")
    mtime = os.path.getmtime(jsonl_path)
    last_mtime = float(context.cursor or "0")
    if mtime > last_mtime:
        context.update_cursor(str(mtime))
        yield dg.RunRequest()
```

This sensor is optional. The weekly schedule is the primary trigger. The sensor provides a way to also trigger the pipeline ad-hoc when the scraper is run manually outside of Dagster.

---

## 4. Code Organization

### Directory Structure

```
src/litmatch/
├── __init__.py
├── definitions.py              # @definitions, load resources, load assets
├── defs/
│   ├── __init__.py
│   ├── assets/
│   │   ├── __init__.py
│   │   ├── extract.py          # raw_books asset
│   │   ├── validate.py         # validated_books + quarantined_records (multi_asset)
│   │   ├── transform.py        # cleaned_books asset
│   │   ├── load.py             # load_books asset
│   │   └── embedding.py        # book_embeddings asset (Phase 3)
│   ├── jobs/
│   │   ├── __init__.py
│   │   └── scraper.py          # trigger_scrape op + scrape_job definition
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── database.py         # DatabaseResource
│   │   ├── scrapyd.py          # ScrapydResource
│   │   ├── path.py             # PathResource
│   │   └── embedding_model.py  # EmbeddingModelResource (Phase 3)
│   ├── schedules/
│   │   ├── __init__.py
│   │   └── weekly.py           # weekly_etl_schedule
│   ├── sensors/
│   │   ├── __init__.py
│   │   └── file_sensor.py      # new_scrape_data_sensor (optional)
│   └── utils/
│       ├── __init__.py
│       ├── validation.py       # validate_record(), schema definitions
│       ├── transforms.py       # fix_publish_date(), encode_rating(), normalize_name()
│       └── db_operations.py    # get_or_create(), upsert_book(), prepare_review()
```

### File Size Guidelines

- Each asset file: 50-150 lines (asset function + docstring + metadata emission).
- Each resource file: 30-80 lines (resource class + methods).
- Each utility file: 50-200 lines (pure functions, well-tested).
- `definitions.py`: 20-40 lines (wiring only).

### Naming Conventions

- **Assets**: noun phrases describing the data they produce (`raw_books`, `cleaned_books`, `book_embeddings`).
- **Ops**: verb phrases describing the action they perform (`trigger_scrape`).
- **Resources**: noun phrases with `Resource` suffix (`DatabaseResource`, `ScrapydResource`).
- **Utility functions**: verb phrases describing the transformation (`fix_publish_date`, `encode_rating`, `validate_record`).

---

## 5. Error Handling and Data Quality

### 5.1 Quarantine Strategy

The quarantine operates at the `validate_books` stage. Every raw record passes through `validate_record()`, which returns a list of error strings. Records with zero errors are valid; records with one or more errors are quarantined.

#### Validation Rules

| Field | Rule | Error Message |
|-------|------|---------------|
| `title` | Required, non-empty string | `"missing_title"` |
| `url` | Required, non-empty string, valid URL format | `"missing_url"` or `"invalid_url"` |
| `author` | Required, non-empty string | `"missing_author"` |
| `genres` | Must be a list | `"invalid_genres_type"` |
| `reviews` | Must be a list of dicts | `"invalid_reviews_type"` |
| `reviews[].rating` | Must be one of: Rave, Positive, Mixed, Pan | `"invalid_review_rating: {value}"` |
| `reviews[].url` | Required, non-empty string | `"missing_review_url"` |
| `last_scraped` | Required, parseable datetime | `"invalid_last_scraped"` |
| `publish_date` | If present, must be fixable to a valid date | `"unfixable_publish_date: {value}"` |

#### Quarantine Output Format

Each quarantined record is written as a JSON object containing:

```json
{
  "original_record": { ... },
  "validation_errors": ["missing_title", "invalid_review_rating: Unknown"],
  "quarantined_at": "2026-02-08T03:00:00Z",
  "source_file": "books.jsonl",
  "line_number": 4523
}
```

Quarantined records are written to `{raw_data_dir}/quarantine/quarantine_{run_id}.jsonl`.

#### Metadata Emission

The `validate_books` multi-asset emits structured metadata visible in the Dagster UI:

```python
context.add_output_metadata(
    metadata={
        "total_records": len(raw_books),
        "valid_records": len(valid),
        "quarantined_records": len(quarantined),
        "quarantine_rate": f"{len(quarantined) / len(raw_books) * 100:.1f}%",
        "errors_by_type": {error_type: count for error_type, count in error_counts.items()},
    },
    output_name="validated_books",
)
```

### 5.2 Error Handling by Stage

| Stage | Error Type | Behavior |
|-------|-----------|----------|
| `raw_books` | JSONL parse error on a line | Log warning, skip line, continue. Emit `parse_errors` count in metadata. |
| `raw_books` | File not found | Raise `dg.Failure` with descriptive message. Asset fails. |
| `validate_books` | Validation failure | Route to quarantine. Never fails the asset. |
| `cleaned_books` | Transformation error (e.g., unparseable date after validation) | Should not occur if validation is correct. If it does, log error, skip record, emit `transform_errors` count. |
| `load_books` | Database constraint violation (e.g., unique URL conflict) | Handle via upsert logic. Log and continue. |
| `load_books` | Database connection failure | Raise `dg.Failure`. Asset fails. Dagster retry policy handles retries. |
| `trigger_scrape` | Scrapyd unreachable | Raise `dg.Failure`. Job fails. |
| `trigger_scrape` | Scrape job times out | Configurable timeout (default: 4 hours). Raise `dg.Failure` after timeout. |

### 5.3 Retry Policy

Apply a retry policy to the `load_books` asset and the `trigger_scrape` op to handle transient failures:

```python
@dg.asset(
    retry_policy=dg.RetryPolicy(
        max_retries=2,
        delay=60,
        backoff=dg.Backoff.EXPONENTIAL,
    ),
)
def load_books(...):
    ...
```

---

## 6. Scraper Orchestration

### Recommendation: Scrapyd API Approach

**Decision:** Keep the scraper in its own Scrapyd container. Dagster orchestrates it via HTTP calls to the Scrapyd API.

### Rationale

| Factor | Scrapyd API | Subprocess in Dagster Container |
|--------|------------|-------------------------------|
| **Dependency isolation** | Scraper deps (Scrapy, Twisted, rotating-proxies, fake-useragent, scrapyd-client) stay in their own container. | All deps must be installed in the Dagster container, significantly increasing image size and potential conflicts. |
| **Existing infrastructure** | Scrapyd is already containerized and working with a proven Dockerfile. | Must rebuild from scratch, duplicating effort. |
| **Container size** | Dagster container stays lean (~500MB). | Dagster container bloats with Scrapy deps (~1GB+). |
| **Operational coupling** | Scraper and Dagster can be updated independently. | Version changes to either affect the other. |
| **Observability** | Scrapyd provides job status via API. Dagster polls and logs progress. | Direct subprocess output captured in Dagster logs, but less structured. |
| **Shared output** | Podman volume shared between Scrapyd and Dagster containers. Well-established pattern. | No volume needed (same container), but tighter coupling. |
| **Complexity** | Slightly more complex (HTTP polling loop). | Simpler invocation, but more complex container build. |

The Scrapyd API approach wins on dependency isolation, maintainability, and alignment with the existing infrastructure.

### Implementation Details

#### ScrapydResource

```python
import dagster as dg
import requests
import time


class ScrapydResource(dg.ConfigurableResource):
    scrapyd_url: str = "http://scrapyd:6800"
    poll_interval_seconds: int = 30
    timeout_seconds: int = 14400  # 4 hours

    def schedule_crawl(self, project: str = "bookmarks", spider: str = "bookmarks") -> str:
        response = requests.post(
            f"{self.scrapyd_url}/schedule.json",
            data={"project": project, "spider": spider},
        )
        response.raise_for_status()
        result = response.json()
        if result.get("status") != "ok":
            raise dg.Failure(
                description=f"Scrapyd schedule failed: {result}",
            )
        return result["jobid"]

    def get_job_status(self, project: str, job_id: str) -> str:
        response = requests.get(
            f"{self.scrapyd_url}/listjobs.json",
            params={"project": project},
        )
        response.raise_for_status()
        jobs = response.json()
        for job in jobs.get("finished", []):
            if job["id"] == job_id:
                return "finished"
        for job in jobs.get("running", []):
            if job["id"] == job_id:
                return "running"
        for job in jobs.get("pending", []):
            if job["id"] == job_id:
                return "pending"
        return "unknown"

    def wait_for_completion(self, project: str, job_id: str) -> None:
        elapsed = 0
        while elapsed < self.timeout_seconds:
            status = self.get_job_status(project, job_id)
            if status == "finished":
                return
            if status == "unknown":
                raise dg.Failure(
                    description=f"Scrapyd job {job_id} not found in any queue",
                )
            time.sleep(self.poll_interval_seconds)
            elapsed += self.poll_interval_seconds
        raise dg.Failure(
            description=f"Scrapyd job {job_id} timed out after {self.timeout_seconds}s",
        )
```

#### Shared Volume Configuration

In `compose.yaml`, the Dagster service and Scrapyd service share a volume:

```yaml
dagster:
  volumes:
    - shared_scraper_output:/data/raw

scrapyd:
  volumes:
    - shared_scraper_output:/scraper/output
```

The Dagster `PathResource` is configured with `RAW_DATA_DIR=/data/raw/raw` (matching the Scrapy FEEDS output path `output/raw/books.jsonl`, which maps to `/data/raw/raw/books.jsonl` inside the Dagster container).

---

## 7. Testing Strategy

### 7.1 Unit Tests

Located in `tests/unit/`. Test pure transformation and validation functions in isolation.

#### Test Files

| File | Tests |
|------|-------|
| `tests/unit/test_validation.py` | `validate_record()` with valid records, missing fields, invalid types, bad ratings, edge cases (empty strings, null values). |
| `tests/unit/test_transforms.py` | `fix_publish_date()` with good dates, known bad dates (0209, 0000, -0001), unparseable dates, empty/None input. `encode_rating()` with all four valid ratings and invalid input. `normalize_name()` with whitespace, encoding issues. |
| `tests/unit/test_db_operations.py` | `get_or_create()` logic tested with mock sessions. `prepare_review()` with duplicate URL handling. Rating encoding edge cases. |

#### Example

```python
import pytest
from litmatch.defs.utils.validation import validate_record

class TestValidateRecord:
    def test_valid_record_returns_no_errors(self, valid_book_record):
        errors = validate_record(valid_book_record)
        assert errors == []

    def test_missing_title_returns_error(self, valid_book_record):
        record = {**valid_book_record, "title": ""}
        errors = validate_record(record)
        assert "missing_title" in errors

    def test_invalid_review_rating_returns_error(self, valid_book_record):
        record = {
            **valid_book_record,
            "reviews": [{**valid_book_record["reviews"][0], "rating": "Excellent"}],
        }
        errors = validate_record(record)
        assert any("invalid_review_rating" in e for e in errors)

    def test_missing_url_returns_error(self, valid_book_record):
        record = {k: v for k, v in valid_book_record.items() if k != "url"}
        errors = validate_record(record)
        assert "missing_url" in errors
```

### 7.2 Integration Tests

Located in `tests/integration/`. Test the full asset graph against a real PostgreSQL instance.

#### Test Database

Use a separate PostgreSQL container for tests. Configuration via `conftest.py`:

```python
import pytest
from sqlmodel import create_engine, SQLModel, Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://testuser:testpassword@localhost:5433/testdb",
)

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)

@pytest.fixture
def test_session(test_engine):
    with Session(test_engine) as session:
        yield session
        session.rollback()
```

A `compose.test.yaml` override provides the test database:

```yaml
services:
  test-db:
    image: pgvector/pgvector:pg18
    environment:
      POSTGRES_DB: testdb
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpassword
    ports:
      - "5433:5432"
```

#### Test Files

| File | Tests |
|------|-------|
| `tests/integration/test_extract.py` | `raw_books` asset reads a test JSONL fixture file. Verifies record count, handles malformed lines. |
| `tests/integration/test_validate.py` | Full validation pipeline with mixed valid/invalid records. Verifies split between validated and quarantined outputs. |
| `tests/integration/test_load.py` | `load_books` asset inserts records into test database. Verifies books, authors, publishers, genres, reviews, critics, publications are created correctly. Tests upsert behavior (update on newer scrape date, skip on older). |
| `tests/integration/test_full_pipeline.py` | End-to-end test materializing `raw_books` -> `validated_books` -> `cleaned_books` -> `load_books` against test database with a fixture JSONL file. Verifies final database state. |

#### Test Fixtures

Create a small test JSONL file at `tests/fixtures/test_books.jsonl` containing ~10 records: 7 valid, 3 with various validation errors (missing title, invalid rating, malformed reviews list).

### 7.3 Running Tests

```bash
# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests (requires test database running)
podman compose -f compose.yaml -f compose.test.yaml up -d test-db
uv run pytest tests/integration/ -v

# All tests with coverage
uv run pytest --cov=src/litmatch --cov-report=term-missing

# Tests by marker
uv run pytest -m unit
uv run pytest -m integration
```

### 7.4 Test Configuration in pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Unit tests (no external dependencies)",
    "integration: Integration tests (requires test database)",
]
```

---

## 8. Deployment

### 8.1 Podman Compose Services

Add three new services to `compose.yaml`: `dagster-webserver`, `dagster-daemon`, and a shared `dagster-code` (user code server). The user code server pattern separates code loading from the webserver and daemon, allowing code updates without restarting the control plane.

#### Updated compose.yaml (Dagster additions)

```yaml
services:
  # ... existing db, backend, scrapyd services ...

  dagster-code:
    build:
      context: .
      dockerfile: Dockerfile.dagster
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      SCRAPYD_URL: http://scrapyd:6800
      RAW_DATA_DIR: /data/raw/raw
    volumes:
      - shared_scraper_output:/data/raw
      - dagster_storage:/opt/dagster/dagster_home/storage
    depends_on:
      - db
      - scrapyd

  dagster-webserver:
    build:
      context: .
      dockerfile: Dockerfile.dagster
    command: ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "workspace.yaml"]
    environment:
      DAGSTER_HOME: /opt/dagster/dagster_home
    volumes:
      - dagster_storage:/opt/dagster/dagster_home/storage
    ports:
      - "3000:3000"
    depends_on:
      - dagster-code

  dagster-daemon:
    build:
      context: .
      dockerfile: Dockerfile.dagster
    command: ["dagster-daemon", "run"]
    environment:
      DAGSTER_HOME: /opt/dagster/dagster_home
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      SCRAPYD_URL: http://scrapyd:6800
      RAW_DATA_DIR: /data/raw/raw
    volumes:
      - shared_scraper_output:/data/raw
      - dagster_storage:/opt/dagster/dagster_home/storage
    depends_on:
      - dagster-code
      - db
      - scrapyd

volumes:
  postgres_data:
  shared_scraper_output:
  dagster_storage:
```

### 8.2 Dagster Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /opt/dagster/app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY backend/ ./backend/

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

# Copy Dagster instance config
COPY dagster.yaml /opt/dagster/dagster_home/dagster.yaml
COPY workspace.yaml /opt/dagster/dagster_home/workspace.yaml

ENV DAGSTER_HOME=/opt/dagster/dagster_home

# Default: run the gRPC user code server
CMD ["dagster", "code-server", "start", "-m", "litmatch.definitions"]
```

### 8.3 workspace.yaml

```yaml
load_from:
  - grpc_server:
      host: dagster-code
      port: 4000
```

### 8.4 dagster.yaml (Updated)

```yaml
run_storage:
  module: dagster.core.storage.runs
  class: SqliteRunStorage
  config:
    base_dir: /opt/dagster/dagster_home/storage

event_log_storage:
  module: dagster.core.storage.event_log
  class: SqliteEventLogStorage
  config:
    base_dir: /opt/dagster/dagster_home/storage

schedule_storage:
  module: dagster.core.storage.schedules
  class: SqliteScheduleStorage
  config:
    base_dir: /opt/dagster/dagster_home/storage

python_logs:
  managed_python_loggers:
    - sqlalchemy.engine
```

**Note:** SQLite-based storage is sufficient for a single-machine deployment with weekly runs. If concurrent runs become necessary, migrate to PostgreSQL-backed Dagster storage (Dagster can share the same Postgres instance or use a dedicated one).

---

## 9. Phased Roadmap

### Phase 1: Core Dagster Pipeline

**Goal:** A working, modular, well-tested pipeline that Dagster orchestrates end-to-end, from scraper trigger to database load, with quarantine for bad records and a weekly schedule.

#### Steps

| Step | Description | Dependencies | Files |
|------|-------------|-------------|-------|
| 1.1 | Create `DatabaseResource` | None | `defs/resources/database.py` |
| 1.2 | Create `ScrapydResource` | None | `defs/resources/scrapyd.py` |
| 1.3 | Create `PathResource` | None | `defs/resources/path.py` |
| 1.4 | Create validation utilities | None | `defs/utils/validation.py` |
| 1.5 | Create transformation utilities | None | `defs/utils/transforms.py` |
| 1.6 | Create database operation utilities | 1.1 | `defs/utils/db_operations.py` |
| 1.7 | Create `raw_books` asset | 1.3 | `defs/assets/extract.py` |
| 1.8 | Create `validated_books` + `quarantined_records` multi-asset | 1.4, 1.7 | `defs/assets/validate.py` |
| 1.9 | Create `cleaned_books` asset | 1.5, 1.8 | `defs/assets/transform.py` |
| 1.10 | Create `load_books` asset | 1.1, 1.6, 1.9 | `defs/assets/load.py` |
| 1.11 | Create `trigger_scrape` op + job | 1.2 | `defs/jobs/scraper.py` |
| 1.12 | Create weekly schedule | 1.7-1.11 | `defs/schedules/weekly.py` |
| 1.13 | Create file sensor (optional) | 1.3, 1.7 | `defs/sensors/file_sensor.py` |
| 1.14 | Wire everything in `definitions.py` | 1.1-1.13 | `definitions.py` |
| 1.15 | Remove dead code (`raw_data`, `cleaned_data`, orphaned helpers) | 1.14 | `defs/assets.py` (delete) |
| 1.16 | Write unit tests | 1.4-1.6 | `tests/unit/` |
| 1.17 | Write integration tests | 1.7-1.10 | `tests/integration/` |
| 1.18 | Update `dagster.yaml` | 1.14 | `dagster.yaml` |
| 1.19 | Update `pyproject.toml` (test deps, markers) | 1.16-1.17 | `pyproject.toml` |

#### Success Criteria

- [ ] `dg dev` launches and shows the full asset graph (5 assets + 1 job)
- [ ] Manually materializing `raw_books` -> `validated_books` -> `cleaned_books` -> `load_books` succeeds end-to-end
- [ ] Quarantined records are written to a JSONL file with error annotations
- [ ] Asset metadata shows record counts, quarantine rates, and error summaries in the Dagster UI
- [ ] `trigger_scrape` op successfully starts and monitors a Scrapyd job (tested against running Scrapyd container)
- [ ] Weekly schedule is visible and can be toggled in the Dagster UI
- [ ] No hardcoded paths or database URLs in asset/resource code
- [ ] Old `defs/assets.py` is deleted; no orphaned assets remain
- [ ] Unit test coverage >= 80% for `utils/` modules
- [ ] Integration tests pass against a test database

---

### Phase 2: Podman Compose Deployment

**Goal:** Dagster runs as Podman Compose services (webserver, daemon, code server) alongside the existing stack. The full pipeline can be triggered and monitored from the Dagster web UI accessible at port 3000.

#### Steps

| Step | Description | Dependencies | Files |
|------|-------------|-------------|-------|
| 2.1 | Create `Dockerfile.dagster` | Phase 1 complete | `Dockerfile.dagster` |
| 2.2 | Create `workspace.yaml` | 2.1 | `workspace.yaml` |
| 2.3 | Update `dagster.yaml` for containerized storage | Phase 1 | `dagster.yaml` |
| 2.4 | Add Dagster services to `compose.yaml` | 2.1-2.3 | `compose.yaml` |
| 2.5 | Configure shared volume between Scrapyd and Dagster | 2.4 | `compose.yaml` |
| 2.6 | Verify end-to-end pipeline in Podman | 2.4-2.5 | Manual testing |
| 2.7 | Update `CLAUDE.md` with new Podman commands | 2.6 | `CLAUDE.md` |
| 2.8 | Update `Makefile` with Dagster targets | 2.6 | `Makefile` |

#### Success Criteria

- [ ] `podman compose up --build -d` starts all services (db, backend, scrapyd, dagster-webserver, dagster-daemon, dagster-code)
- [ ] Dagster web UI is accessible at `http://localhost:3000`
- [ ] Full pipeline can be triggered from the Dagster UI and completes successfully
- [ ] Weekly schedule activates automatically and the daemon executes it
- [ ] Dagster containers can read `books.jsonl` from the shared volume after a scrape completes
- [ ] Dagster containers can connect to the PostgreSQL database
- [ ] Container restarts preserve run history and schedule state (persistent volume for `dagster_storage`)

---

### Phase 3: Embedding Generation + Semantic Search

**Goal:** A new Dagster asset generates embeddings for books using a local sentence-transformers model and stores them in a pgvector column. The FastAPI backend gains a semantic search endpoint.

#### Steps

| Step | Description | Dependencies | Files |
|------|-------------|-------------|-------|
| 3.1 | Add `embedding` column (Vector type) to `Book` model | None | `backend/db/models.py` |
| 3.2 | Create database migration for embedding column | 3.1 | Manual SQL or Alembic |
| 3.3 | Add `sentence-transformers` to `pyproject.toml` | None | `pyproject.toml` |
| 3.4 | Create `EmbeddingModelResource` | 3.3 | `defs/resources/embedding_model.py` |
| 3.5 | Create `book_embeddings` asset | 3.1, 3.4 | `defs/assets/embedding.py` |
| 3.6 | Update `Dockerfile.dagster` for sentence-transformers deps | 3.3 | `Dockerfile.dagster` |
| 3.7 | Add semantic search endpoint to FastAPI | 3.1 | `backend/app/main.py` |
| 3.8 | Write unit tests for embedding asset | 3.5 | `tests/unit/test_embedding.py` |
| 3.9 | Write integration tests for semantic search | 3.7 | `tests/integration/test_semantic_search.py` |

#### Asset Design: `book_embeddings`

```python
@dg.asset(
    deps=["load_books"],
    retry_policy=dg.RetryPolicy(max_retries=1, delay=30),
)
def book_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
    embedding_model: EmbeddingModelResource,
) -> None:
    """Generate embeddings for books that do not yet have one."""
    with database.get_session() as session:
        books_without_embeddings = session.exec(
            select(Book).where(Book.embedding == None)
        ).all()

    if not books_without_embeddings:
        context.log.info("All books already have embeddings")
        return

    texts = [
        f"{book.title} by {book.author.name if book.author else 'Unknown'}. {book.description}"
        for book in books_without_embeddings
    ]

    # Batch encode (sentence-transformers handles batching internally)
    embeddings = embedding_model.encode(texts)

    with database.get_session() as session:
        for book, embedding in zip(books_without_embeddings, embeddings):
            book_record = session.get(Book, book.id)
            book_record.embedding = embedding
        session.commit()

    context.add_output_metadata({
        "embeddings_generated": len(embeddings),
        "model_name": embedding_model.model_name,
        "dimensions": embedding_model.dimensions,
    })
```

#### EmbeddingModelResource

```python
class EmbeddingModelResource(dg.ConfigurableResource):
    model_name: str = "all-MiniLM-L6-v2"

    _model: Any = None

    @property
    def dimensions(self) -> int:
        model_dimensions = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
        }
        return model_dimensions.get(self.model_name, 384)

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=True)
        return embeddings.tolist()
```

#### Book Model Update

```python
class Book(SQLModel, table=True):
    # ... existing fields ...
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(384)),
    )
```

#### Semantic Search Endpoint

```python
@app.get("/books/semantic-search", response_model=PaginatedResponse[Book])
def semantic_search(
    *,
    session=Depends(get_session),
    q: str = Query(min_length=2, max_length=500),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
):
    # Encode the query using the same model
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_embedding = model.encode([q])[0].tolist()

    offset = (page - 1) * limit
    stmt = (
        select(Book)
        .where(Book.embedding != None)
        .order_by(Book.embedding.cosine_distance(query_embedding))
        .offset(offset)
        .limit(limit)
    )
    # ...
```

**Note:** Loading the model per-request in the search endpoint is inefficient. In production, the model should be loaded once at startup and cached. This is an implementation detail, not an architectural decision.

#### Success Criteria

- [ ] `book_embeddings` asset materializes successfully, generating vectors for all books
- [ ] Embedding column exists in the `book` table with correct dimensions (384)
- [ ] Books that already have embeddings are skipped on subsequent runs (idempotent)
- [ ] Semantic search endpoint returns relevant books for natural language queries
- [ ] Dagster UI shows embedding generation metadata (count, model, dimensions)
- [ ] Podman container for Dagster includes sentence-transformers and can run inference on CPU

---

### Phase 4: Recommender as Dagster Asset (Long-Term)

**Goal:** The SVD recommender training becomes a Dagster asset that reads user ratings from the database, trains a model, and stores the serialized model for the FastAPI backend to load.

**Status:** Intentionally underspecified. Outline only.

#### Outline

- New asset: `trained_recommender_model`
  - Depends on: `load_books` (needs user ratings in DB)
  - Reads: user ratings from PostgreSQL
  - Produces: serialized model artifact (pickle or joblib)
  - Stores to: filesystem path accessible by the FastAPI backend
- New resource: `ModelStorageResource` -- manages model artifact path
- Schedule: retrain weekly (or when sufficient new ratings accumulate, via a sensor)
- Backend: `GET /recommendations/{user_id}` loads the latest model artifact and generates predictions
- Fallback: if user has fewer than N ratings, return popular books instead

#### Open Questions (to resolve when Phase 4 begins)

- Minimum number of user ratings before training is meaningful
- Model evaluation criteria and whether to track RMSE as Dagster metadata
- Whether to use critic reviews, user ratings, or both for training
- Cold-start strategy for new users
- Model versioning and rollback strategy

---

## 10. Architecture Decision Records

### ADR-001: Scrapyd API for Scraper Orchestration

**Context:** Dagster needs to trigger the Scrapy scraper. Two approaches: call the existing Scrapyd API or run Scrapy as a subprocess in the Dagster container.

**Decision:** Use the Scrapyd API approach.

**Consequences:**
- Positive: Dependency isolation, smaller Dagster container, independent scaling, reuses existing infrastructure.
- Negative: Slightly more complex polling logic, requires shared volume for data transfer, adds HTTP coupling between containers.
- Alternatives: Subprocess (simpler invocation, tighter coupling, bloated container).

**Status:** Accepted

### ADR-002: Local Filesystem for Raw Data Storage

**Context:** Raw scraper output (`books.jsonl`) needs to be stored somewhere accessible to both the scraper and the Dagster pipeline.

**Decision:** Use local filesystem via Podman volumes with the path configured as a Dagster resource (`PathResource`). No object storage (MinIO/S3) in the current phase.

**Consequences:**
- Positive: Zero additional infrastructure, simple, works with existing Podman volume setup.
- Negative: Data tied to host machine, no built-in versioning or durability beyond host disk.
- Migration path: Replace `PathResource` with an S3/MinIO IO manager when needed. Downstream assets do not change because they receive data via Dagster's asset dependency system, not direct file reads.

**Status:** Accepted

### ADR-003: Multi-Asset Quarantine Pattern

**Context:** Invalid records need to be separated from valid ones during validation. Options: (a) raise and fail, (b) log and skip silently, (c) quarantine to a separate output.

**Decision:** Use a `@multi_asset` that produces both `validated_books` and `quarantined_records` simultaneously. Quarantined records are written to JSONL with error annotations.

**Consequences:**
- Positive: Pipeline never fails due to bad data. Full visibility into data quality via Dagster metadata. Quarantined records are inspectable and re-processable. Clear audit trail.
- Negative: Slightly more complex asset definition (multi-asset). Quarantine files accumulate and need periodic cleanup.
- Alternatives: Fail-fast (too aggressive for 13K records with known data quality issues), skip silently (loses visibility into problems).

**Status:** Accepted

---

## 11. Future Considerations

### Migration to Object Storage

When raw data durability or multi-environment support becomes necessary:
1. Add a MinIO container to `compose.yaml`.
2. Replace `PathResource` with Dagster's `S3IOManager` configured for MinIO.
3. Update the Scrapyd container to write directly to MinIO (via `scrapy-s3pipeline` or a post-crawl upload step).
4. No changes to downstream assets -- they receive data via Dagster's dependency system.

### PostgreSQL-Backed Dagster Storage

If concurrent pipeline runs, longer run history, or multi-instance Dagster deployment becomes necessary:
1. Create a dedicated `dagster` database in the existing PostgreSQL instance (or use a separate instance).
2. Update `dagster.yaml` to use `PostgresRunStorage`, `PostgresEventLogStorage`, `PostgresScheduleStorage`.
3. Add `dagster-postgres` to `pyproject.toml`.

### CI/CD Integration

When CI is implemented:
1. Add GitHub Actions workflow that runs `uv run pytest tests/unit/` on every PR.
2. Add a separate job that starts a test database via `podman compose -f compose.test.yaml` and runs integration tests.
3. Optionally add a Dagster asset materialization test (dry run) as a CI step.

### Alembic for Database Migrations

The current approach uses `SQLModel.metadata.create_all()`, which is additive (creates new tables/columns but never modifies or drops existing ones). When schema changes become more complex (especially the embedding column in Phase 3):
1. Add Alembic to the project.
2. Generate migration scripts for schema changes.
3. Run migrations as a Dagster op or a pre-deployment step.

### Scaling Beyond 100K Books

If the dataset grows significantly:
- Replace in-memory data passing between assets with `FilesystemIOManager` or `S3IOManager`.
- Add partitions to the `load_books` asset (partition by first letter, genre, or scrape batch).
- Consider chunked embedding generation with checkpointing.
- Evaluate whether the single PostgreSQL instance can handle the vector search load (pgvector performance degrades beyond ~100K vectors without HNSW indexing -- ensure `CREATE INDEX ... USING hnsw` is applied).

---

## Appendix: Environment Variables

| Variable | Required | Default | Used By |
|----------|----------|---------|---------|
| `DATABASE_URL` | Yes | `postgresql://bookuser:bookpassword@localhost:5432/bookdb` | Dagster, Backend |
| `SCRAPYD_URL` | No | `http://scrapyd:6800` | Dagster |
| `RAW_DATA_DIR` | No | `/data/raw/raw` | Dagster |
| `POSTGRES_DB` | Yes | (none) | Podman Compose |
| `POSTGRES_USER` | Yes | (none) | Podman Compose |
| `POSTGRES_PASSWORD` | Yes | (none) | Podman Compose |
| `PROXY_TOKEN` | Yes | (none) | Scrapyd |
| `DAGSTER_HOME` | No | `/opt/dagster/dagster_home` | Dagster containers |
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | Dagster (Phase 3) |

## Appendix: Dependency Changes to pyproject.toml

### Phase 1 Additions

```toml
dependencies = [
    # ... existing ...
    "requests>=2.31.0",        # For ScrapydResource HTTP calls
]

[dependency-groups]
dev = [
    # ... existing ...
    "pytest>=8.0",
    "pytest-cov>=4.0",
]
```

### Phase 3 Additions

```toml
dependencies = [
    # ... existing ...
    "sentence-transformers>=2.2.0",
    "torch>=2.0.0",            # CPU-only; use torch-cpu if available
]
```
