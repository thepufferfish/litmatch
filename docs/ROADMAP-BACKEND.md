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

## Phase 3: Recommendations API — PLANNED

**Depends on:** Pipeline Phase 4 (trained recommender model)

### 3.1 Recommendations Endpoint
- `GET /recommendations/{user_id}` (or `GET /recommendations/` scoped to current user)
- Requires Bearer auth; users can only request their own recommendations
- Loads trained SVD model artifact from filesystem
- Returns `list[Book]` with recommendation scores
- Fallback: popular books (by average critic rating or review count) if user has < N ratings
- Response shape: `PaginatedResponse[Book]` or custom shape with scores

### 3.2 Semantic Search Endpoint (Pipeline Phase 3 dependency)
- `GET /books/semantic-search?q={query}&page={n}&limit={n}`
- Encodes query using sentence-transformers model
- Queries pgvector for cosine similarity
- Returns same `PaginatedResponse[Book]` shape
- May replace or augment existing ILIKE search
- Performance concern: model loading on startup, not per-request

### 3.3 User Profile Data
- `GET /users/me` — return current user's profile data
- May include: username, join date, total ratings count, average rating given

### 3.4 Additional Endpoints (Potential)
- `DELETE /ratings/{rating_id}` — remove a rating

### Open Questions
- Should recommendations be computed on-demand or pre-computed and cached?
- If cached, what invalidation strategy? (Retrain schedule in Dagster)
- Should the endpoint return a confidence/predicted rating alongside each book?
- Cold-start strategy for new users and new books?

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
