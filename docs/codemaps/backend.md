# Backend Codemap

> Freshness: 2026-02-15 | Auto-generated from source analysis

## Module Graph

```
backend/
  app/
    main.py -----> config.py, auth.py, rate_limit.py, queries.py, recommendations.py, db/models.py
    auth.py -----> config.py, db/models.py
    config.py ---> (env vars only)
    rate_limit.py -> slowapi
    queries.py --> db/models.py (Review)
    recommendations.py -> db/models.py (Book, Review, UserRating, BookGenreLink), queries.py
  db/
    models.py ---> sqlmodel, pydantic, pgvector
  database.py --> alembic (migrations)
  tests/
    conftest.py, test_auth, test_config, test_endpoints,
    test_models, test_rate_limit, test_search,
    test_recommendations, test_security_headers
```

## API Endpoints

| Method | Path | Auth | Rate Limit | Response |
|--------|------|------|------------|----------|
| POST | /auth/register | No | 3/min | AuthResponse |
| POST | /auth/login | No | 5/min | AuthResponse |
| POST | /auth/refresh | Cookie | -- | AuthResponse |
| POST | /auth/logout | Cookie | -- | 200 |
| GET | /books/ | No | -- | PaginatedResponse[BookRead] |
| GET | /books/search | No | -- | PaginatedResponse[BookRead] |
| GET | /books/{id} | No | -- | BookRead |
| GET | /reviews/{book_id} | No | -- | list[Review] |
| GET | /genres/ | No | -- | list[Genre] |
| GET | /genres/grouped | No | -- | GroupedGenresResponse |
| GET | /users/me | Bearer | -- | UserProfile |
| GET | /users/me/rated-books/ | Bearer | -- | PaginatedResponse[BookRead] |
| GET | /recommendations/ | Optional | -- | RecommendationResponse |
| GET | /ratings/ | Bearer | -- | list[UserRating] |
| POST | /ratings/ | Bearer | 30/min | UserRating |
| DELETE | /ratings/{book_id} | Bearer | -- | 200 |
| GET | /health | No | -- | 200 |

## Key Files

### `app/config.py` -- Environment Configuration
- `SECRET_KEY` (required), `DATABASE_URL` (required)
- `CORS_ORIGINS` (default: localhost:5173), `COOKIE_SECURE` (default: true)
- `ACCESS_TOKEN_EXPIRE_MINUTES` = 15, `REFRESH_TOKEN_EXPIRE_DAYS` = 7

### `app/auth.py` -- JWT + Refresh Token Logic
- `create_access_token(user_id, username)` -> JWT string
- `create_refresh_token()` -> cryptographic random string
- `decode_bearer_token(credentials)` -> FastAPI dependency
- `store_refresh_token()`, `validate_refresh_token()`, `revoke_refresh_token()`

### `app/main.py` -- FastAPI Application
- CORS middleware, rate limiter, all route handlers
- `get_session()` -- DB session dependency
- `get_current_user()` -- auth dependency chain
- `escape_like()` -- SQL LIKE wildcard sanitization
- Sorting: title, date, rating (avg critic), reviews (count)
- Category filtering: fiction, nonfiction, all
- Genre filtering by slug with subgenre support

### `app/queries.py` -- Reusable Query Components
- `build_rating_subquery()` -- avg_rating and review_count aggregation from Review table

### `app/recommendations.py` -- Recommendation Engine
- `compute_user_embedding(session, user_id)` -- weighted avg of book embeddings (rating-2 weight)
- `find_nearest_books(session, embedding, ...)` -- pgvector cosine distance query
- `get_popular_books(session, ...)` -- fallback: books ranked by avg critic rating
- `MIN_RATINGS` = 5 (threshold for personalized vs popular)
- `CategoryFilter` -- Literal["all", "fiction", "nonfiction"]

### `app/rate_limit.py` -- SlowAPI Setup
- `limiter` instance keyed by remote IP

### `db/models.py` -- Database Tables + API Schemas
- 11 SQLModel tables: Author, Publisher, Book, Genre, BookGenreLink, Critic, Publication, Review, User, UserRating, RefreshToken
- Book and Review have pgvector `Vector(384)` embedding columns
- API schemas: PaginatedResponse, BookRead, GenreRead, AuthorRead, PublisherRead, ReviewRead, UserPublic, UserCreate, UserProfile, RatingCreate, AuthResponse, RecommendationMeta, RecommendationResponse, GroupedGenresResponse, GenreSimple

### `database.py` -- Schema Init Script
- Enables pgvector extension, runs Alembic migrations

## Dependency Stack

```
FastAPI + Uvicorn (ASGI)
+-- SQLModel (ORM) -> SQLAlchemy 2.x -> psycopg2
+-- python-jose (JWT)
+-- bcrypt (password hashing)
+-- slowapi (rate limiting)
+-- pgvector (vector extension + cosine distance)
+-- pydantic v2 (validation)
+-- alembic (migrations)
```
