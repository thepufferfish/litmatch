# Backend Codemap

> Freshness: 2026-02-08 | Auto-generated from source analysis

## Module Graph

```
backend/
  app/
    main.py ──→ config.py, auth.py, rate_limit.py, db/models.py
    auth.py ──→ config.py, db/models.py
    config.py ──→ (env vars only)
    rate_limit.py ──→ slowapi
  db/
    models.py ──→ sqlmodel, pydantic, pgvector
  database.py ──→ db/models.py, sqlmodel
  tests/
    conftest.py, test_auth, test_config, test_endpoints,
    test_models, test_rate_limit, test_search
```

## API Endpoints

| Method | Path | Auth | Rate Limit | Response |
|--------|------|------|------------|----------|
| POST | /auth/register | No | 3/min | AuthResponse |
| POST | /auth/login | No | 5/min | AuthResponse |
| POST | /auth/refresh | Cookie | — | AuthResponse |
| POST | /auth/logout | Cookie | — | 200 |
| GET | /books/ | No | — | PaginatedResponse[BookRead] |
| GET | /books/search | No | — | PaginatedResponse[BookRead] |
| GET | /books/{id} | No | — | BookRead |
| GET | /reviews/{book_id} | No | — | list[Review] |
| GET | /genres/ | No | — | list[Genre] |
| GET | /ratings/ | Bearer | — | list[UserRating] |
| POST | /ratings/ | Bearer | 30/min | UserRating |

## Key Files

### `app/config.py` — Environment Configuration
- `SECRET_KEY` (required), `DATABASE_URL` (required)
- `CORS_ORIGINS` (default: localhost:5173), `COOKIE_SECURE` (default: true)
- `ACCESS_TOKEN_EXPIRE_MINUTES` = 15, `REFRESH_TOKEN_EXPIRE_DAYS` = 7

### `app/auth.py` — JWT + Refresh Token Logic
- `create_access_token(user_id, username)` → JWT string
- `create_refresh_token()` → cryptographic random string
- `decode_bearer_token(credentials)` → FastAPI dependency
- `store_refresh_token()`, `validate_refresh_token()`, `revoke_refresh_token()`

### `app/main.py` — FastAPI Application
- CORS middleware, rate limiter, all route handlers
- `get_session()` — DB session dependency
- `get_current_user()` — auth dependency chain
- `escape_like()` — SQL LIKE wildcard sanitization

### `app/rate_limit.py` — SlowAPI Setup
- `limiter` instance keyed by remote IP

### `db/models.py` — Database Tables + API Schemas
- 11 SQLModel tables: Author, Publisher, Book, Genre, BookGenreLink, Critic, Publication, Review, User, UserRating, RefreshToken
- 10 Pydantic schemas: PaginatedResponse, GenreRead, AuthorRead, PublisherRead, BookRead, UserBase, UserCreate, UserPublic, RatingCreate, AuthResponse

### `database.py` — Schema Init Script
- Enables pgvector extension, creates all tables via SQLModel

## Dependency Stack

```
FastAPI + Uvicorn (ASGI)
├── SQLModel (ORM) → SQLAlchemy 2.x → psycopg2
├── python-jose (JWT)
├── bcrypt (password hashing)
├── slowapi (rate limiting)
├── pgvector (vector extension)
└── pydantic v2 (validation)
```
