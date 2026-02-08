# ETL Pipeline & Scraper Roadmap

**Tech Stack:** Dagster + Scrapy/Scrapyd + PostgreSQL + pgvector + sentence-transformers (planned)

**Reference Spec:** [dagster-spec.md](../dagster-spec.md)

## Scraper: bookmarks.reviews — DONE

### Current State
- Scrapy sitemap spider crawling bookmarks.reviews
- Incremental scraping via `lastmod` metadata comparison
- Deployed via Scrapyd in Docker container (port 6800)
- Output: `books.jsonl` to shared Docker volume
- Proxy rotation and user-agent middleware configured
- Data volume: ~13,000 books

### Key Files
- `scraper/bookmarks/spiders/bookmarks_spider.py` — main spider
- `scraper/bookmarks/settings.py` — Scrapy settings
- `scraper/bookmarks/middlewares.py` — custom middleware
- `scraper/bookmarks/proxies.py` — proxy rotation
- `scraper/bookmarks/pipelines.py` — item pipelines
- `scraper/Dockerfile` — Scrapyd container

### Future Scraper Work (Unplanned)
- Potential: expand to additional review aggregators
- Potential: scrape additional metadata (awards, bestseller lists)

## Pipeline Phase 1: Core Dagster Pipeline — IN PROGRESS

### Asset Graph

```
raw_books ──> validated_books + validation_errors ──> cleaned_books ──> load_books
```

### Completed

| Item | File | Status |
|------|------|--------|
| DatabaseResource | `defs/resources/database.py` | DONE |
| PathResource | `defs/resources/path.py` | DONE |
| ScrapydResource (placeholder) | `defs/resources/scrapyd.py` | PARTIAL |
| Validation utilities | `defs/utils/validation.py` | DONE |
| Transformation utilities | `defs/utils/transforms.py` | DONE |
| DB operation utilities | `defs/utils/db_operations.py` | DONE |
| `raw_books` asset | `defs/assets/extract.py` | DONE |
| `validate_raw_books` multi-asset | `defs/assets/validate.py` | DONE |
| `cleaned_books` asset | `defs/assets/transform.py` | DONE |
| `load_books` asset | `defs/assets/load.py` | DONE |
| `definitions.py` wiring | `definitions.py` | DONE |
| Unit tests (validation, transforms, db_ops) | `tests/dagster/` | DONE |
| Asset integration tests | `tests/dagster/test_assets.py` | DONE |

### Remaining

| Item | Priority | Spec Reference |
|------|----------|---------------|
| Implement ScrapydResource methods (schedule_crawl, poll, wait) | HIGH | dagster-spec.md Section 6 |
| Create `trigger_scrape` op + `scrape_job` | HIGH | Step 1.11 |
| Create `weekly_etl_schedule` (cron `0 3 * * 0`) | HIGH | Step 1.12 |
| Create file sensor (optional) | LOW | Step 1.13 |
| Add metadata emission to all assets (record counts, rates) | MEDIUM | Section 5.1 |
| Add retry policy to `load_books` (max_retries=2, exponential backoff) | MEDIUM | Section 5.3 |
| Write quarantine records to JSONL file | MEDIUM | Section 5.1 |
| Wire ScrapydResource in `definitions.py` | HIGH | Step 1.14 |
| Delete `assets_legacy.py` | LOW | Step 1.15 |
| Add test markers to `pyproject.toml` | LOW | Step 1.19 |
| Create `compose.test.yaml` for test database | MEDIUM | Section 7.2 |

### Phase 1 Success Criteria
- [ ] `dg dev` launches and shows the full asset graph (4 data assets + 1 job)
- [ ] Full materialization succeeds end-to-end (raw_books through load_books)
- [ ] Quarantined records are written to JSONL with error annotations
- [ ] Asset metadata visible in Dagster UI (record counts, quarantine rates)
- [ ] `trigger_scrape` op starts and monitors a Scrapyd job
- [ ] Weekly schedule is visible and toggleable in Dagster UI
- [ ] No hardcoded paths or database URLs
- [ ] Unit test coverage >= 80% for utils/ modules
- [ ] Integration tests pass against test database

## Pipeline Phase 2: Docker Compose Deployment — NOT STARTED

**Depends on:** Phase 1 completion

### Work Items

| Item | File | Priority |
|------|------|----------|
| Create `Dockerfile.dagster` | `Dockerfile.dagster` | HIGH |
| Create `workspace.yaml` (gRPC code server) | `workspace.yaml` | HIGH |
| Update `dagster.yaml` for SQLite storage paths | `dagster.yaml` | HIGH |
| Add dagster-code, dagster-webserver, dagster-daemon to `compose.yaml` | `compose.yaml` | HIGH |
| Configure shared volume (scrapyd ↔ dagster) | `compose.yaml` | HIGH |
| Add `dagster_storage` volume | `compose.yaml` | HIGH |
| Verify end-to-end in Docker | Manual | HIGH |
| Update CLAUDE.md with new Docker commands | `CLAUDE.md` | MEDIUM |
| Update Makefile with Dagster targets | `Makefile` | LOW |
| Update RUNBOOK.md with Dagster service docs | `docs/RUNBOOK.md` | MEDIUM |

### Phase 2 Success Criteria
- [ ] `docker compose up --build -d` starts all services including Dagster
- [ ] Dagster web UI accessible at http://localhost:3000
- [ ] Pipeline can be triggered from Dagster UI and completes
- [ ] Weekly schedule activates and daemon executes it
- [ ] Container restarts preserve run history (persistent volume)

## Pipeline Phase 3: Embeddings & Semantic Search — NOT STARTED

**Depends on:** Phase 2 completion, backend model change (embedding column)

### Work Items

| Item | File | Priority |
|------|------|----------|
| Add embedding column (`Vector(384)`) to Book model | `backend/db/models.py` | HIGH |
| Database migration for embedding column | Manual SQL or Alembic | HIGH |
| Add `sentence-transformers` to `pyproject.toml` | `pyproject.toml` | HIGH |
| Create `EmbeddingModelResource` | `defs/resources/embedding_model.py` | HIGH |
| Create `book_embeddings` asset | `defs/assets/embedding.py` | HIGH |
| Update `Dockerfile.dagster` for torch/sentence-transformers | `Dockerfile.dagster` | HIGH |
| Add semantic search endpoint to FastAPI | `backend/app/main.py` | HIGH |
| Unit and integration tests | `tests/` | MEDIUM |

### Architecture Decision
- Model: `all-MiniLM-L6-v2` (384 dimensions, CPU-friendly)
- Storage: pgvector column on Book table
- Incremental: only generate for books without embeddings
- See: dagster-spec.md Section 9 Phase 3

## Pipeline Phase 4: Recommender as Dagster Asset — NOT STARTED

**Depends on:** Phase 3 completion, sufficient user ratings

### Work Items (Outline)

| Item | Description |
|------|-------------|
| `trained_recommender_model` asset | Reads user ratings, trains SVD, stores model artifact |
| `ModelStorageResource` | Manages model artifact path |
| Retrain schedule | Weekly or sensor-based (new ratings threshold) |
| Backend endpoint | `GET /recommendations/{user_id}` loads model and predicts |
| Fallback strategy | Popular books when insufficient user data |

### Open Questions
- Minimum user ratings before training is meaningful
- Model evaluation criteria (RMSE tracking as Dagster metadata)
- Critic reviews vs. user ratings for training data
- Cold-start strategy for new users
- Model versioning and rollback

## Architecture Decisions

### ADR-001: Scrapyd API for Scraper Orchestration
**Decision:** Keep scraper in Scrapyd container, orchestrate via HTTP. Dagster polls for completion.
**Rationale:** Dependency isolation, smaller Dagster container, independent scaling.

### ADR-002: Local Filesystem for Raw Data
**Decision:** Docker volumes with configurable PathResource. No object storage yet.
**Migration path:** Replace PathResource with S3IOManager when needed.

### ADR-003: Multi-Asset Quarantine Pattern
**Decision:** `@multi_asset` produces both valid and quarantined outputs. Pipeline never fails on bad data.

## Future Considerations

- **Object Storage (MinIO/S3):** When raw data durability or multi-environment support is needed
- **PostgreSQL-backed Dagster storage:** When concurrent runs or longer history is needed
- **CI/CD integration:** GitHub Actions for unit tests on PRs, integration tests with test DB
- **Alembic migrations:** When schema changes become complex (embedding column)
- **Scaling beyond 100K books:** Partitioned assets, chunked embedding generation, HNSW indexing

## Testing Status

| Test | Coverage | Status |
|------|----------|--------|
| `test_validation.py` | validate_book_record, validate_review | DONE |
| `test_transforms.py` | fix_publish_date, encode_rating, clean_critic_name, classify_fiction | DONE |
| `test_db_operations.py` | upsert_book, get_or_create, prepare_reviews | DONE |
| `test_assets.py` | Asset materialization | DONE |
| Integration tests (full pipeline with test DB) | End-to-end | NOT STARTED |
| `compose.test.yaml` (test database config) | Infrastructure | NOT STARTED |
