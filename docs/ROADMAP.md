# LitMatch Roadmap

## Project Summary

LitMatch is a book discovery and recommendation platform with five components:

1. **Scraper** — Crawls bookmarks.reviews, writes to PostgreSQL staging table
2. **ETL Pipeline** — Dagster orchestration: validate, transform, load to PostgreSQL
3. **Backend** — FastAPI REST API with JWT auth
4. **Frontend** — React SPA for browsing, searching, rating books
5. **Recommender** — Embedding-based recommendations using sentence-transformers + pgvector (see [ROADMAP-RECOMMENDER.md](ROADMAP-RECOMMENDER.md))

## Overall Status

| Component | Phase | Status |
|-----------|-------|--------|
| Scraper | Operational | DONE |
| ETL Pipeline | Phase 1 (Core pipeline) | DONE |
| ETL Pipeline | Phase 2 (Podman deployment) | DONE |
| ETL Pipeline | Phase 3 (Review + book embeddings) | DONE |
| Backend | Phase 1 (Browse API) | DONE |
| Backend | Phase 2 (JWT Auth & Ratings) | DONE |
| Backend | Phase 2.5 (Browse enhancements) | DONE |
| Backend | Phase 3 (Recommendations API) | DONE |
| Backend | Phase 4 (Semantic search + optimization) | NOT STARTED |
| Frontend | Phase 1 (Browse & Discover) | DONE |
| Frontend | Phase 2 (Auth & Ratings) | DONE |
| Frontend | Phase 2.5 (Browse enhancements) | DONE |
| Frontend | Phase 3 (Recommendations & Profile) | DONE |
| Frontend | Phase 4 (Semantic search UI) | NOT STARTED |
| Recommender | Standalone SVD prototype | DONE (superseded by embedding approach) |
| Deployment | Phase A (Local dev improvements) | DONE |
| Deployment | Phase B (LAN server) | NOT STARTED |
| Deployment | Phase C (Dagster compose integration) | DONE |

## Milestones

### Milestone 1: Full-Stack MVP — DONE

Users can browse books, search, filter by genre, view critic reviews.

- React SPA with BrowsePage, BookDetailPage
- FastAPI with paginated books, search, reviews, genres endpoints
- Dagster ETL pipeline loading scraped data into PostgreSQL

### Milestone 2: Authenticated User Experience — DONE

Users can register, log in, and rate books.

- JWT authentication (access token + httpOnly refresh cookie)
- Registration and login pages
- Star rating component on book detail pages
- Rate limiting on auth and rating endpoints
- CORS configuration

### Milestone 3: Production-Ready Pipeline — DONE

Dagster pipeline runs fully automated in Podman containers with sensor-driven execution.

- Dagster scraper trigger via `crawl_books` asset (ScrapydResource)
- Three jobs: `etl_pipeline` (full ETL + embeddings), `crawl` (trigger Scrapyd only), `embedding_pipeline` (embeddings only)
- Two sensors: `staging_data_sensor` (staging table watch) and `startup_crawl_sensor` (first-deploy seed)
- Podman Compose: dagster-code (gRPC), dagster-webserver (UI), dagster-daemon (sensors)
- Health checks and startup ordering for all services
- Integration test suite with `compose.test.yaml`

**All optional enhancements completed:**
- Weekly schedule (`weekly_crawl_schedule` triggers `crawl` every Sunday at midnight UTC, default STOPPED)
- Asset metadata emission for Dagster UI (record counts, validation rates)
- Retry policies on `load_books` (max 2 retries, exponential backoff)
- Quarantine JSONL file output (timestamped files with error annotations)
- See: [Pipeline Roadmap](ROADMAP-PIPELINE.md)

### Milestone 4: Personalized Recommendations — MOSTLY DONE

Users receive book recommendations based on their ratings, powered by sentence-transformer embeddings and pgvector nearest-neighbor search. Replaces the standalone SVD prototype with a fully integrated embedding-based system.

**Architecture**: Review text -> sentence-transformers embeddings (384-dim) -> per-book averages -> signed-weight user taste vectors -> pgvector cosine similarity search, separated by fiction/non-fiction.

**Implementation phases** (see [Recommender Roadmap](ROADMAP-RECOMMENDER.md) for full details):
1. Review embeddings (Dagster asset + DB schema) — Pipeline Phase 3a — **DONE**
2. Book embeddings (averaged review embeddings) — Pipeline Phase 3b — **DONE**
3. User embeddings + recommendation API — Backend Phase 3 — **DONE**
4. Fiction/non-fiction separation + frontend — Frontend Phase 3 — **DONE**
5. Semantic search + optimization — Backend Phase 4 + Frontend Phase 4

**Completed:**
- Pipeline: `review_embeddings` + `book_embeddings` Dagster assets, `EmbeddingModelResource`
- Backend: `GET /recommendations/` endpoint (auth required, category filter, rate limited), `GET /users/me`
- Frontend: ProfilePage with fiction/nonfiction tabs, `useRecommendations` hook, `RecommendationGrid` component
- User embeddings filtered by category (fiction/nonfiction) for more targeted recommendations
- Weekly schedule triggers `crawl` job; `staging_data_sensor` then triggers ETL pipeline

**Remaining:**
- Backend Phase 4: `GET /books/semantic-search` endpoint
- Frontend Phase 4: Semantic search toggle in SearchBar
- Integration tests for recommendation endpoints
- See: [Recommender Roadmap](ROADMAP-RECOMMENDER.md), [Backend Roadmap](ROADMAP-BACKEND.md), [Frontend Roadmap](ROADMAP-FRONTEND.md), [Pipeline Roadmap](ROADMAP-PIPELINE.md)

### Milestone 5: LAN Deployment — PARTIALLY DONE

Application deployed as a self-contained Podman Compose stack. Local dev stack is complete; LAN server deployment remains.

**Sub-milestones:**

#### 5a: Local Development Stack — DONE
- Podman Compose starts DB + backend + scraper + Dagster with health checks and startup ordering
- Backend has `/health` endpoint verifying database connectivity
- Frontend served via Nginx container (port 8080) with SPA routing and `/api` proxy
- `.env.example` documents all required/optional variables
- Dagster services (code, webserver, daemon) fully integrated in compose

#### 5b: LAN Server Stack — NOT STARTED
- Caddy reverse proxy builds and serves frontend as static files
- All services behind Caddy (single port 80 exposed to LAN)
- systemd service for auto-start on boot
- Automated daily database backup with 30-day retention
- Firewall configured (only port 80 exposed)
- mDNS (Avahi) for `litmatch.local` hostname
- Update/redeploy procedure documented

See: [Deployment Roadmap](ROADMAP-DEPLOY.md)

## Cross-Component Dependencies

```
Scraper ─────────────┐
                     v
               ETL Pipeline ──────────────┐
                     │                     │
                     v                     v
              PostgreSQL+pgvector    review_embeddings (Dagster)
                     │                     │
                     v                     v
              FastAPI Backend ────── book_embeddings (Dagster)
                     │
                     v
              React Frontend
```

**Key dependency chains:**
- ~~Frontend Phase 3 → Backend Phase 3 (recommendations endpoint)~~ — **resolved, both DONE**
- Frontend Phase 4 → Backend Phase 4 (semantic search endpoint)
- ~~Backend Phase 3 → Pipeline Phase 3 (review + book embeddings)~~ — **resolved, both DONE**
- ~~Pipeline Phase 3 (embeddings) → Pipeline Phase 2 (Podman deployment)~~ — **resolved, both DONE**
- Deployment Phase B → Deployment Phase A — **unblocked**

## Detailed Roadmaps

| Document | Scope |
|----------|-------|
| [ROADMAP-RECOMMENDER.md](ROADMAP-RECOMMENDER.md) | Embedding-based recommendation system architecture and phases |
| [ROADMAP-FRONTEND.md](ROADMAP-FRONTEND.md) | React SPA phases, components, testing |
| [ROADMAP-BACKEND.md](ROADMAP-BACKEND.md) | FastAPI endpoints, auth, security hardening |
| [ROADMAP-PIPELINE.md](ROADMAP-PIPELINE.md) | Scraper + Dagster ETL + embedding pipeline |
| [ROADMAP-DEPLOY.md](ROADMAP-DEPLOY.md) | Local dev stack + LAN server deployment + backup/recovery |

## Archived Documents

| Document | Notes |
|----------|-------|
| [archive/SPEC.md](archive/SPEC.md) | Original frontend UI/UX specification (Phases 1-2 fully implemented) |
| [archive/PLAN.md](archive/PLAN.md) | Original implementation plan (Phases 1-2 fully executed) |
| [dagster-spec.md](../dagster-spec.md) | Pipeline architecture specification (authoritative, still active) |
