# ETL Pipeline & Scraper Roadmap

**Tech Stack:** Dagster + Scrapy/Scrapyd + PostgreSQL + pgvector + sentence-transformers

**Reference Spec:** [dagster-spec.md](../dagster-spec.md)

## Scraper: bookmarks.reviews — DONE

### Current State
- Scrapy sitemap spider crawling bookmarks.reviews
- Incremental scraping via `lastmod` metadata comparison
- Deployed via Scrapyd in Podman container (port 6800)
- Output: writes scraped items to `raw_books_staging` PostgreSQL table
- Proxy rotation and user-agent middleware configured
- Data volume: ~13,000 books

### Key Files
- `scraper/bookmarks/spiders/bookmarks_spider.py` — main spider
- `scraper/bookmarks/settings.py` — Scrapy settings
- `scraper/bookmarks/middlewares.py` — custom middleware
- `scraper/bookmarks/proxies.py` — proxy rotation
- `scraper/Dockerfile` — Scrapyd container

### Future Scraper Work (Unplanned)
- Potential: expand to additional review aggregators
- Potential: scrape additional metadata (awards, bestseller lists)

## Pipeline Phase 1: Core Dagster Pipeline — DONE

### Asset Graph

```
crawl_books ──> raw_books ──> validated_books + validation_errors ──> cleaned_books ──> load_books
```

### Completed

| Item | File | Status |
|------|------|--------|
| DatabaseResource | `defs/resources/database.py` | DONE |
| PathResource | `defs/resources/path.py` | DONE |
| ScrapydResource (schedule, job_status, is_healthy) | `defs/resources/scrapyd.py` | DONE |
| Validation utilities | `defs/utils/validation.py` | DONE |
| Transformation utilities | `defs/utils/transforms.py` | DONE |
| DB operation utilities | `defs/utils/db_operations.py` | DONE |
| `crawl_books` asset (Scrapyd trigger + poll) | `defs/assets/crawl.py` | DONE |
| `raw_books` asset (deps on crawl_books) | `defs/assets/extract.py` | DONE |
| `validated_books` / `validation_errors` multi-asset | `defs/assets/validate.py` | DONE |
| `cleaned_books` asset | `defs/assets/transform.py` | DONE |
| `load_books` asset | `defs/assets/load.py` | DONE |
| `etl_pipeline` job (ETL + embeddings) | `defs/jobs.py` | DONE |
| `crawl` job (trigger Scrapyd crawl only) | `defs/jobs.py` | DONE |
| `staging_data_sensor` (staging table watch) | `defs/sensors/data_freshness.py` | DONE |
| `startup_crawl_sensor` (first-deploy seed) | `defs/sensors/startup_crawl.py` | DONE |
| `definitions.py` wiring (all assets, jobs, sensors, resources) | `definitions.py` | DONE |
| Test markers in `pyproject.toml` (unit, integration) | `pyproject.toml` | DONE |
| `compose.test.yaml` for test database | `compose.test.yaml` | DONE |
| Unit tests (validation, transforms, db_ops, assets, sensors) | `tests/dagster/` | DONE |
| Integration tests (health, DB, ETL, API) | `tests/integration/` | DONE |
| `assets_legacy.py` removed | — | DONE |

### Phase 1 Enhancements (Optional) — ALL DONE

| Item | Status | Implementation |
|------|--------|----------------|
| Metadata emission to all assets | DONE | All 5 assets emit structured metadata (record counts, validation rates, etc.) via `MaterializeResult` or `Output` |
| Retry policy for `load_books` | DONE | `RetryPolicy(max_retries=2, delay=30, backoff=EXPONENTIAL)` added to load_books asset |
| Write quarantine records to JSONL file | DONE | `validation_errors` persisted to timestamped JSONL files with microsecond-precision filenames |
| Weekly crawl schedule | DONE | `weekly_crawl_schedule` triggers `crawl` every Sunday at midnight UTC (default STOPPED) |

### Phase 1 Success Criteria
- [x] `dg dev` launches and shows the full asset graph (5 assets + 2 jobs)
- [x] Full materialization succeeds end-to-end (crawl_books through load_books)
- [x] Quarantined records are written to JSONL with error annotations
- [x] Asset metadata visible in Dagster UI (record counts, quarantine rates)
- [x] `crawl_books` asset starts and monitors a Scrapyd job
- [x] Weekly schedule is visible and toggleable in Dagster UI
- [x] No hardcoded paths or database URLs
- [x] Unit test coverage >= 80% for utils/ modules (100% achieved)
- [x] Integration tests pass against test database

## Pipeline Phase 2: Podman Compose Deployment — DONE

### Completed

| Item | File | Status |
|------|------|--------|
| `Dockerfile.dagster` (multi-stage, uv-based) | `Dockerfile.dagster` | DONE |
| `workspace.yaml` (gRPC code server on port 4000) | `workspace.yaml` | DONE |
| `dagster.yaml` (logging config) | `dagster.yaml` | DONE |
| dagster-code service (gRPC, depends on db + scrapyd) | `compose.yaml` | DONE |
| dagster-webserver service (UI on port 3000) | `compose.yaml` | DONE |
| dagster-daemon service (sensors, depends on backend) | `compose.yaml` | DONE |
| PostgreSQL staging table (scrapyd writes, dagster reads) | `compose.yaml` | DONE |
| `dagster_storage` volume | `compose.yaml` | DONE |
| Health checks on all Dagster services | `compose.yaml` | DONE |
| Startup ordering (db → dagster-code → webserver/daemon) | `compose.yaml` | DONE |
| CLAUDE.md updated with Podman commands | `CLAUDE.md` | DONE |
| Makefile with Dagster targets (`dagster-logs`, etc.) | `Makefile` | DONE |
| RUNBOOK.md with Dagster service docs | `docs/RUNBOOK.md` | DONE |
| End-to-end verification in Podman | Manual | DONE |

### Phase 2 Success Criteria
- [x] `podman compose up --build -d` starts all services including Dagster
- [x] Dagster web UI accessible at http://localhost:3000
- [x] Pipeline can be triggered from Dagster UI and completes
- [x] Weekly schedule triggers `crawl` every Sunday at midnight UTC (default STOPPED)
- [x] Container restarts preserve run history (persistent volume)

## Pipeline Phase 3: Review + Book Embeddings — DONE

**Depends on:** Phase 2 completion (**unblocked**), backend model changes (embedding columns)

**Reference:** [Recommender Roadmap](ROADMAP-RECOMMENDER.md) Phases 1-2

This phase implements the embedding foundation for the recommender system. Review-level embeddings are the atomic unit; book embeddings are computed as averages of review embeddings.

### Phase 3a: Review Embeddings (Recommender Phase 1) — DONE

| Item | File | Status |
|------|------|--------|
| Add `embedding` Vector(384) column to Review model | `backend/db/models.py` | DONE |
| Add migration SQL to `init_db()` | `backend/database.py` | DONE |
| Add `sentence-transformers`, `torch`, `numpy` to pyproject.toml | `pyproject.toml` | DONE |
| Create `EmbeddingModelResource` (lazy-loaded model, allowlist security) | `defs/resources/embedding_model.py` | DONE |
| Create `review_embeddings` asset (incremental, batch 256) | `defs/assets/embedding.py` | DONE |
| Register resource and asset in definitions.py | `definitions.py` | DONE |
| Update `Dockerfile.dagster` for torch dependencies | `Dockerfile.dagster` | DONE |
| Unit tests (mocked model) | `tests/dagster/test_embedding_asset.py`, `test_embedding_resource.py` | DONE |
| Integration test | `tests/integration/test_embeddings.py` | NOT STARTED |

### Phase 3b: Book Embeddings (Recommender Phase 2) — DONE

| Item | File | Status |
|------|------|--------|
| Add `embedding` Vector(384) column to Book model | `backend/db/models.py` | DONE |
| Add migration SQL for book embedding column | `backend/database.py` | DONE |
| Create `book_embeddings` asset (average review embeddings) | `defs/assets/embedding.py` | DONE |
| Create `embedding_pipeline` job | `defs/jobs.py` | DONE |
| Register in definitions.py | `definitions.py` | DONE |
| Unit tests for averaging logic (21 tests, 99% coverage) | `tests/dagster/test_book_embedding_asset.py` | DONE |
| Integration test for full pipeline | `tests/integration/test_embeddings.py` | NOT STARTED |

### Asset Graph Extension

```
[Existing Pipeline]
crawl_books -> raw_books -> validated_books -> cleaned_books -> load_books
                                                                       |
                                                                       v
                                                              review_embeddings
                                                                       |
                                                                       v
                                                              book_embeddings
```

### Architecture Decisions
- **Model**: `all-MiniLM-L6-v2` (384 dimensions, 80 MB, CPU-friendly, ~15 min for 100K reviews)
- **Storage**: pgvector columns on Review and Book tables (review-level is the atomic unit)
- **Incremental**: only encode reviews/books where `embedding IS NULL`
- **No SVD training**: The standalone surprise-based SVD prototype (`recommender/`) is superseded. User embeddings are computed on-demand in the backend (no Dagster asset needed).
- **Container impact**: Dagster container grows from ~500 MB to ~1.5 GB due to PyTorch CPU
- See: [Recommender Roadmap](ROADMAP-RECOMMENDER.md) ADR-005 through ADR-007

## Architecture Decisions

### ADR-001: Scrapyd API for Scraper Orchestration
**Decision:** Keep scraper in Scrapyd container, orchestrate via HTTP. Dagster polls for completion.
**Rationale:** Dependency isolation, smaller Dagster container, independent scaling.

### ADR-002: PostgreSQL Staging Table for Raw Data
**Decision:** Scrapy writes scraped items to a `raw_books_staging` PostgreSQL table. Dagster reads from this table. Replaced the previous shared Podman volume approach.
**Migration path:** Replace with S3IOManager when needed.

### ADR-003: Multi-Asset Quarantine Pattern
**Decision:** `@multi_asset` produces both valid and quarantined outputs. Pipeline never fails on bad data.

## Future Considerations

- **Embedding recomputation sensor:** Trigger `embedding_pipeline` when new reviews are loaded (Phase 5 of recommender roadmap)
- **HNSW index:** Add to `book.embedding` when book count exceeds 50K (see [Recommender Roadmap](ROADMAP-RECOMMENDER.md) scaling thresholds)
- **Object Storage (MinIO/S3):** When raw data durability or multi-environment support is needed
- **PostgreSQL-backed Dagster storage:** When concurrent runs or longer history is needed
- **CI/CD integration:** GitHub Actions for unit tests on PRs, integration tests with test DB
- **Alembic migrations:** When schema changes become complex
- **Scaling beyond 100K books:** Partitioned assets, chunked embedding generation, HNSW tuning

## Testing Status

| Test | Coverage | Status |
|------|----------|--------|
| `test_validation.py` | validate_book_record, validate_review | DONE |
| `test_transforms.py` | fix_publish_date, encode_rating, clean_critic_name, classify_fiction | DONE |
| `test_db_operations.py` | upsert_book, get_or_create, prepare_reviews | DONE |
| `test_assets.py` | Asset materialization (extract, validate, transform, load) | DONE |
| `test_crawl_asset.py` | Crawl asset + jobs module | DONE |
| `test_scrapyd_resource.py` | ScrapydResource HTTP client | DONE |
| `test_sensors.py` | Staging data sensor | DONE |
| `test_startup_crawl_sensor.py` | Startup crawl sensor state machine | DONE |
| `test_embedding_asset.py` | review_embeddings asset (encoding, batching, idempotency, error handling, NULL/empty text filtering) — 20+ tests | DONE |
| `test_embedding_resource.py` | EmbeddingModelResource (lazy loading, allowlist, encoding) | DONE |
| `test_book_embedding_asset.py` | book_embeddings asset (averaging, idempotency, engine disposal, correctness) — 18+ tests | DONE |
| `test_schedule.py` | Weekly crawl schedule (triggers crawl) | DONE |
| `test_asset_dependencies.py` | Asset dependency validation | DONE |
| `compose.test.yaml` | Test database config with isolated volumes | DONE |
| `test_container_health.py` | Service health and port reachability | DONE |
| `test_database.py` | Schema initialization and connectivity | DONE |
| `test_etl_pipeline.py` | Full ETL pipeline via Dagster GraphQL API | DONE |
| `test_backend_api.py` | REST API endpoints (auth, books, search, ratings) | DONE |
