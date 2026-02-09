# LitMatch Roadmap

## Project Summary

LitMatch is a book discovery and recommendation platform with five components:

1. **Scraper** — Crawls bookmarks.reviews, outputs `books.jsonl`
2. **ETL Pipeline** — Dagster orchestration: validate, transform, load to PostgreSQL
3. **Backend** — FastAPI REST API with JWT auth
4. **Frontend** — React SPA for browsing, searching, rating books
5. **Recommender** — SVD-based collaborative filtering (planned integration)

## Overall Status

| Component | Phase | Status |
|-----------|-------|--------|
| Scraper | Operational | DONE |
| ETL Pipeline | Phase 1 (Core pipeline) | DONE |
| ETL Pipeline | Phase 2 (Podman deployment) | DONE |
| ETL Pipeline | Phase 3 (Embeddings) | NOT STARTED |
| ETL Pipeline | Phase 4 (Recommender training) | NOT STARTED |
| Backend | Phase 1 (Browse API) | DONE |
| Backend | Phase 2 (JWT Auth & Ratings) | DONE |
| Backend | Phase 2.5 (Browse enhancements) | DONE |
| Backend | Phase 3 (Recommendations API) | NOT STARTED |
| Frontend | Phase 1 (Browse & Discover) | DONE |
| Frontend | Phase 2 (Auth & Ratings) | DONE |
| Frontend | Phase 2.5 (Browse enhancements) | DONE |
| Frontend | Phase 3 (Recommendations & Profile) | NOT STARTED |
| Recommender | Standalone prototype | DONE (needs integration) |
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
- Two jobs: `etl_pipeline` (ETL-only) and `crawl_and_load` (full pipeline)
- Two sensors: `data_freshness_sensor` (file-watch) and `startup_crawl_sensor` (first-deploy seed)
- Podman Compose: dagster-code (gRPC), dagster-webserver (UI), dagster-daemon (sensors)
- Health checks and startup ordering for all services
- Integration test suite with `compose.test.yaml`

**Remaining enhancements (optional):**
- Weekly schedule (currently event-driven only via sensors)
- Asset metadata emission for Dagster UI (record counts, rates)
- Retry policies on `load_books`
- Quarantine JSONL file output (validation errors captured in-memory but not persisted)
- See: [Pipeline Roadmap](ROADMAP-PIPELINE.md)

### Milestone 4: Personalized Recommendations — PLANNED

Users receive book recommendations based on their ratings.

**Requires:**
- Pipeline: embedding generation asset, recommender training asset
- Backend: `GET /recommendations/{user_id}` endpoint, semantic search endpoint
- Frontend: profile page, "Recommended for You" section
- See: [Backend Roadmap](ROADMAP-BACKEND.md), [Frontend Roadmap](ROADMAP-FRONTEND.md), [Pipeline Roadmap](ROADMAP-PIPELINE.md)

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
              PostgreSQL+pgvector    Recommender Training
                     │                     │
                     v                     v
              FastAPI Backend ────── Model Artifacts
                     │
                     v
              React Frontend
```

**Key dependency chains:**
- Frontend Phase 3 → Backend Phase 3 (recommendations endpoint)
- Backend Phase 3 → Pipeline Phase 4 (trained recommender model)
- Pipeline Phase 3 (embeddings) → Pipeline Phase 2 (Podman deployment for sentence-transformers) — **unblocked**
- Deployment Phase B → Deployment Phase A — **unblocked**

## Detailed Roadmaps

| Document | Scope |
|----------|-------|
| [ROADMAP-FRONTEND.md](ROADMAP-FRONTEND.md) | React SPA phases, components, testing |
| [ROADMAP-BACKEND.md](ROADMAP-BACKEND.md) | FastAPI endpoints, auth, security hardening |
| [ROADMAP-PIPELINE.md](ROADMAP-PIPELINE.md) | Scraper + Dagster ETL + embeddings + recommender training |
| [ROADMAP-DEPLOY.md](ROADMAP-DEPLOY.md) | Local dev stack + LAN server deployment + backup/recovery |

## Archived Documents

| Document | Notes |
|----------|-------|
| [archive/SPEC.md](archive/SPEC.md) | Original frontend UI/UX specification (Phases 1-2 fully implemented) |
| [archive/PLAN.md](archive/PLAN.md) | Original implementation plan (Phases 1-2 fully executed) |
| [dagster-spec.md](../dagster-spec.md) | Pipeline architecture specification (authoritative, still active) |
