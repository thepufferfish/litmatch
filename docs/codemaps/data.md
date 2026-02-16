# Data Models Codemap

> Freshness: 2026-02-15 | Auto-generated from source analysis

## Entity Relationship Diagram

```
User (1)---->(N) UserRating <(N)----(1) Book
User (1)---->(N) RefreshToken

Book (N)---->(1) Author
Book (N)---->(1) Publisher
Book (N)<--->(N) Genre        [via BookGenreLink]
Book (1)---->(N) Review

Review (N)-->(1) Critic
Review (N)-->(1) Publication

Book.embedding    : Vector(384)  [avg of review embeddings]
Review.embedding  : Vector(384)  [sentence-transformers]
```

## Database Tables (`backend/db/models.py`)

### Core Entities

| Table | PK | Key Columns | Unique Constraints |
|-------|-----|-------------|-------------------|
| book | id | title, author_id, publisher_id, publish_date, description, url, cover, is_fiction, last_scraped, embedding(384) | url |
| author | id | name | name |
| publisher | id | name | name |
| genre | id | name | name |
| book_genre_link | book_id, genre_id | -- | -- |

### Review Entities

| Table | PK | Key Columns | Unique Constraints |
|-------|-----|-------------|-------------------|
| review | id | book_id, critic_id, publication_id, rating (int 1-4), review (text), url, embedding(384) | url |
| critic | id | name | name |
| publication | id | name | name |

### User Entities

| Table | PK | Key Columns | Unique Constraints |
|-------|-----|-------------|-------------------|
| user | id | username, password_hash | username |
| user_rating | id | user_id, book_id, rating (int 1-5), created_at, updated_at | (user_id, book_id) |
| refresh_token | id | user_id, token_hash, expires_at, created_at | token_hash |

## Rating Systems

**Critic ratings** (Review.rating): 1-4 scale mapped from text
| Text | Value |
|------|-------|
| Pan | 1 |
| Mixed | 2 |
| Positive | 3 |
| Rave | 4 |

**User ratings** (UserRating.rating): 1-5 star scale

## API Response Schemas (Pydantic)

```
PaginatedResponse<T>
  items: list[T]
  total: int
  page: int
  limit: int

BookRead
  id, title, publish_date, description, url, cover, is_fiction, last_scraped
  author: AuthorRead {id, name}
  publisher: PublisherRead {id, name}
  genres: list[GenreRead] {id, name}

ReviewRead
  id, book_id, rating, review, url
  critic: {id, name}
  publication: {id, name}

AuthResponse
  access_token: str
  token_type: "bearer"
  user: UserPublic {id, username}

UserProfile
  id: int
  username: str
  rating_count: int

RecommendationResponse
  books: list[BookRead]
  meta: RecommendationMeta {strategy: "personalized"|"popular", total_ratings: int}

GroupedGenresResponse
  fiction: list[GenreSimple {id, name}]
  nonfiction: list[GenreSimple {id, name}]
  unknown: list[GenreSimple {id, name}]
```

## Frontend Types (`frontend/src/types/index.ts`)

```
Author {id, name}
Publisher {id, name}
Genre {id, name}
Critic {id, name}
Publication {id, name}
Review {id, book_id, critic_id, publication_id, rating, review, url, critic, publication}
Book {id, title, author_id, publisher_id, publish_date, description, url, cover, is_fiction, last_scraped, author, publisher, genres}
UserRating {id, user_id, book_id, rating, created_at, updated_at}
UserPublic {id, username}
AuthResponse {access_token, token_type, user}
LoginCredentials {username, password}
RegisterCredentials {username, password}
RatingCreate {book_id, rating}
PaginatedResponse<T> {items, total, page, limit}
UserProfile {id, username, rating_count}
RecommendationMeta {strategy, total_ratings}
RecommendationResponse {books, meta}
GroupedGenresResponse {fiction, nonfiction, unknown}
GenreSimple {id, name}
```

## ETL Data Pipeline

### Raw Record (raw_books_staging table, JSONB item_data column)
```json
{
  "title": "str",
  "author": "str",
  "publisher": "str",
  "publish_date": "str | null",
  "description": "str",
  "url": "str",
  "cover": "str",
  "genres": ["str"],
  "last_scraped": "str (ISO datetime)",
  "reviews": [{
    "critic": "str",
    "publication": "str",
    "rating": "Rave|Positive|Mixed|Pan",
    "review": "str",
    "url": "str"
  }]
}
```

### Validation Rules (`utils/validation.py`)
- Book: required non-empty fields -- title, url, author, last_scraped
- Review: required field -- review (text); rating must be one of {Rave, Positive, Mixed, Pan}

### Transform Pipeline (`utils/transforms.py`)
| Field | Transform |
|-------|-----------|
| publish_date | str -> `date` (fixes bad years: 0209, 0000, -0001 -> 2019) |
| last_scraped | str -> `datetime` |
| rating | "Rave"->4, "Positive"->3, "Mixed"->2, "Pan"->1 |
| critic | Strip trailing commas, fallback to publication or "Unknown" |
| is_fiction | Derived from genres: Fiction->True, Non-Fiction->False, else->None |

### Load Strategy (`utils/db_operations.py`)
- Upsert by URL (unique key)
- Newer scrape -> update, older scrape -> skip
- Get-or-create for: Author, Publisher, Genre, Critic, Publication
- Review dedup by URL; NULL URLs allowed (multiple reviews without URLs)
- Nested savepoints for per-book error isolation

### Embedding Pipeline
- `review_embeddings`: sentence-transformers (all-MiniLM-L6-v2) -> 384-dim vectors, incremental, batched
- `book_embeddings`: average of review embeddings per book
- Used by recommendation engine for cosine distance search
