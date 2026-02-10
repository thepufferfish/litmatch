# Backend Roadmap

**Tech Stack:** FastAPI + SQLModel + PostgreSQL (pgvector) + bcrypt + python-jose + slowapi

**Archived Spec:** [archive/SPEC.md](archive/SPEC.md) (API sections)

## Phase 1: Browse API — DONE

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/books/?page={n}&limit={n}&genre={id}` | Paginated book list with genre filter. `PaginatedResponse[Book]` |
| `GET` | `/books/search?q={query}&page={n}&limit={n}` | Text search (ILIKE). Ranked: exact > title > author. Min 2 chars. |
| `GET` | `/books/{book_id}` | Single book with relations. 404 if not found. |
| `GET` | `/reviews/{book_id}` | Reviews for a book. Returns `[]` if none. |
| `GET` | `/genres/` | All genres. |

### Implementation Details
- Page-based pagination, `PaginatedResponse` envelope with `items`, `total`, `page`, `limit`
- SQL injection prevention via `escape_like()` for search patterns
- Search ranking via SQL `CASE` expression
- Limit clamped to 1-100

## Phase 2: JWT Auth & Ratings — DONE

### Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| `POST` | `/auth/register` | No | 3/min/IP | Create user, return JWT + set refresh cookie |
| `POST` | `/auth/login` | No | 5/min/IP | Validate credentials, return JWT + set refresh cookie |
| `POST` | `/auth/refresh` | Cookie | — | Rotate refresh token, return new JWT |
| `POST` | `/auth/logout` | Cookie | — | Revoke refresh token, clear cookie |
| `GET` | `/ratings/` | Bearer | — | Current user's ratings (optionally filtered by book_id) |
| `POST` | `/ratings/` | Bearer | 30/min/user | Create or update rating (upsert). Body: `{book_id, rating}` |

### Architecture
- `backend/app/config.py` — centralized config, requires SECRET_KEY and DATABASE_URL env vars
- `backend/app/auth.py` — JWT encode/decode, refresh token hash/store/validate/revoke
- `backend/app/rate_limit.py` — slowapi limiter
- Refresh tokens stored as SHA-256 hashes
- Token rotation on refresh (revoke old, issue new)
- httpOnly + Secure + SameSite=Strict cookies
- Cookie path configurable via REFRESH_COOKIE_PATH
- Generic error messages prevent user enumeration

### Database Models

| Model | Purpose |
|-------|---------|
| Book | Central entity |
| Author, Publisher | One-to-many with Book |
| Genre | Many-to-many with Book via BookGenreLink |
| Review, Critic, Publication | Critic reviews |
| User | Authentication |
| UserRating | User star ratings (1-5) |
| RefreshToken | JWT refresh token storage |

## Phase 2.5: Browse Enhancements — DONE

Additions to the browse and detail APIs implemented after Phase 2.

### Endpoints Updated

| Method | Endpoint | Enhancement |
|--------|----------|-------------|
| `GET` | `/books/?sort={option}` | Sorting by rating, reviews, date, title (asc/desc) |
| `GET` | `/books/search?sort={option}` | Sorting support on search results |
| `GET` | `/books/`, `/books/{id}` | `avg_critic_rating` and `review_count` annotations |
| `GET` | `/reviews/{book_id}` | Critic name, publication name, review URL in response |
| `GET` | `/health` | Database connectivity check (returns 200 or 503) |

### Implementation Details
- Sort options: `rating_desc`, `reviews_desc`, `date_desc`, `date_asc`, `title_asc`, `title_desc`
- Rating computed via `func.avg(Review.rating)` subquery, rounded to 1 decimal
- Null dates sorted last via `nulls_last()`
- Secondary sort by title for deterministic ordering

## Phase 3: Recommendations API — DONE

**Depends on:** Pipeline Phase 3 (review + book embeddings stored in PostgreSQL) — **resolved**

**Reference:** [Recommender Roadmap](ROADMAP-RECOMMENDER.md) Phase 3

### Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| `GET` | `/users/me` | Bearer | 30/min | Current user's profile (id, username, rating_count) |
| `GET` | `/recommendations/?limit={n}&category={cat}` | Bearer | 15/min | Personalized or popular book recommendations |

### 3.1 Recommendations Endpoint
- `GET /recommendations/` scoped to current authenticated user
- Requires Bearer auth, rate limited to 15/min
- Computes user taste embedding on-demand via signed-weight average of rated book embeddings (weight = rating - 2)
- User embeddings filtered by category — only ratings for books matching the requested category (fiction/nonfiction) contribute to the embedding
- Fallback: popular books (by average critic rating) when user has < 5 ratings
- Query params: `limit` (1-50, default 10), `category` ("fiction" | "nonfiction" | "all")
- Already-rated books excluded from results
- Response includes `meta.strategy` ("personalized" or "popular"), `meta.rating_count`, `meta.category`

### 3.2 User Profile Data
- `GET /users/me` — returns `UserProfile` (id, username, rating_count)
- Requires Bearer auth, rate limited to 30/min

### 3.3 Recommendation Logic Module
- File: `backend/app/recommendations.py`
- `_compute_weighted_embedding()` — signed-weight average of (rating, embedding) pairs
- `compute_user_embedding()` — fetches user's ratings with book embeddings, filters by category, delegates to `_compute_weighted_embedding()`
- `find_nearest_books()` — pgvector cosine distance search with fiction/nonfiction filter
- `get_popular_books()` — fallback for cold-start users (by average critic rating)

### 3.4 Response Models
- `RecommendationResponse` — `{items: BookRead[], meta: RecommendationMeta}`
- `RecommendationMeta` — `{strategy, rating_count, category}`
- `UserProfile` — `{id, username, rating_count}`

**Note:** The response shape differs from the original roadmap spec. Instead of returning separate `fiction` and `nonfiction` arrays in a single response, the API returns `items` for the requested category. The frontend makes separate calls per category (fiction/nonfiction tabs).

### 3.5 Additional Endpoints (Potential)
- `DELETE /ratings/{rating_id}` — remove a rating

### Design Decisions (Resolved)
- **On-demand computation**: User embeddings computed at request time (sub-millisecond for 5-50 ratings). No precomputation or cache invalidation needed at current scale.
- **Cold-start**: Users with < 5 ratings get popular books fallback.
- **Category-scoped embeddings**: User embedding is filtered by fiction/nonfiction category, so fiction recommendations reflect only fiction taste and vice versa.
- **No confidence score**: Cosine distance could be normalized to a match % in the future, but deferred for now.

## Phase 4: Semantic Search + Optimization — PLANNED

**Depends on:** Phase 3 + Pipeline Phase 3 (book embeddings)

**Reference:** [Recommender Roadmap](ROADMAP-RECOMMENDER.md) Phase 5

### 4.1 Semantic Search Endpoint
- `GET /books/semantic-search?q={query}&page={n}&limit={n}`
- No authentication required
- Encodes query using sentence-transformers model (loaded once at FastAPI startup via `lru_cache`)
- Queries pgvector for cosine similarity on book embeddings
- Returns `PaginatedResponse[BookRead]` (same shape as existing search)
- Query validation: 2-500 chars

### 4.2 Performance Optimization
- HNSW index on `book.embedding` if >10K books with embeddings
- Response caching for recommendations (TTL 5 min) if latency exceeds targets
- Embedding recomputation sensor in Dagster (trigger on new reviews)

### 4.3 Backend Dockerfile Impact
- Backend container needs sentence-transformers + PyTorch CPU (~1 GB added to image)
- Model loaded once at startup, not per-request

## Security Hardening (Pre-Production)

| Item | Status |
|------|--------|
| SECRET_KEY required (no default) | DONE |
| DATABASE_URL required (no default) | DONE |
| CORS origins configurable | DONE |
| Cookie Secure flag configurable | DONE |
| Rate limiting on auth endpoints | DONE |
| Generic error messages (anti-enumeration) | DONE |
| Security headers (CSP, X-Frame-Options, HSTS) | NOT STARTED |
| Global exception handler (no stack traces) | NOT STARTED |
| Alembic for database migrations | NOT STARTED |
| Input sanitization audit | NOT STARTED |

## Testing Status

| Test | Coverage | Status |
|------|----------|--------|
| `test_auth.py` | JWT auth module | DONE |
| `test_config.py` | Config module | DONE |
| `test_endpoints.py` | API endpoints (register, login, books, ratings) | DONE |
| `test_models.py` | Database models | DONE |
| `test_rate_limit.py` | Rate limiting | DONE |
| `test_search.py` | Search endpoint | DONE |
| `test_backend_api.py` (integration) | Full REST API via running compose stack | DONE |
| `test_database.py` (integration) | Schema initialization and connectivity | DONE |
| `test_backend_api.py` recommendations (integration) | `/recommendations/` and `/users/me` endpoints | NOT STARTED |
