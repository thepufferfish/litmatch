# LitMatch Recommender System MVP -- Architectural Roadmap

## 1. Executive Summary

This document specifies the architecture for LitMatch's embedding-based recommendation system. The system creates semantic embeddings from critic review text using sentence-transformers, computes per-book embeddings by averaging review embeddings, builds per-user taste profiles by signed-weight averaging of book embeddings (weight = rating - 2, so low ratings repel and high ratings attract), and serves recommendations via pgvector nearest-neighbor search, separated by fiction and non-fiction.

This replaces the standalone surprise-based SVD prototype in `recommender/recommender.py` with a fully integrated, production-ready pipeline spanning Dagster assets, PostgreSQL storage, FastAPI endpoints, and React frontend components.

### Scope

Five implementation phases, each independently shippable:

| Phase | Deliverable | Depends On |
|-------|------------|------------|
| Phase 1 | Review embeddings (Dagster asset + DB schema) — **DONE** | Existing ETL pipeline |
| Phase 2 | Book embeddings (averaged review embeddings) — **DONE** | Phase 1 |
| Phase 3 | User embeddings + recommendation API | Phase 2 |
| Phase 4 | Fiction/non-fiction separation + frontend | Phase 3 |
| Phase 5 | Precomputation, caching, and optimization | Phase 4 |

---

## 2. Current State Analysis

### Existing Infrastructure

**Database schema** (`backend/db/models.py`):
- `Book` has `is_fiction: bool | None` field -- already classifies fiction/non-fiction via genre analysis in the ETL transform step
- `Review` has `review: str` (the full review text) and `book_id: int` foreign key
- `UserRating` has `user_id`, `book_id`, `rating` (1-5 integer)
- pgvector extension is already enabled in `init_db()` at `backend/database.py`
- No embedding columns exist yet on any table

**Dagster pipeline** (`src/litmatch/`):
- Five-stage asset graph: `crawl_books` -> `raw_books` -> `validate_raw_books` -> `cleaned_books` -> `load_books`
- `DatabaseResource` at `src/litmatch/defs/resources/database.py` provides engine access
- `dagster-spec.md` already sketches a `book_embeddings` asset and `EmbeddingModelResource` for Phase 3 -- this roadmap supersedes that sketch with review-level granularity

**Recommender prototype** (`recommender/recommender.py`):
- Reads from `reviews.csv` (manual export)
- Uses surprise library SVD on critic reviews (treating critics as "users")
- Completely standalone, no database or API integration
- Will be replaced, not extended

**Data volume**:
- ~13,000 books
- Multiple reviews per book (variable, typically 3-20)
- Estimated ~100,000 reviews total
- User ratings: sparse (early-stage product)

### Key Constraints

1. **CPU-only inference**: No GPU available in the Podman deployment. Model must be CPU-friendly.
2. **Single machine**: All services run on one host. No distributed compute.
3. **Small user base**: Cold-start is the primary challenge, not scale.
4. **Review text is the richest signal**: Critic reviews are professional, substantive text (100-500 words typically). This is far richer than title+description for embedding quality.

---

## 3. Architecture Design Decisions

### ADR-005: Embedding Model Selection

**Context**: Need a sentence-transformer model that produces meaningful embeddings from review text, runs on CPU within reasonable time for ~100K reviews, and fits in a Podman container.

**Decision**: Use `all-MiniLM-L6-v2` (384 dimensions).

| Factor | all-MiniLM-L6-v2 | all-mpnet-base-v2 | e5-small-v2 |
|--------|-------------------|--------------------|----|
| Dimensions | 384 | 768 | 384 |
| Model size | 80 MB | 420 MB | 130 MB |
| CPU encoding speed (100K texts) | ~15 min | ~45 min | ~20 min |
| Semantic quality (MTEB) | Good | Best | Good |
| Container image overhead | +~400 MB (with PyTorch CPU) | +~750 MB | +~500 MB |
| pgvector storage per row | 1,536 bytes | 3,072 bytes | 1,536 bytes |

**Rationale**: MiniLM-L6-v2 offers the best trade-off for this use case. The 384-dimension space is sufficient for ~13K books. The smaller model size keeps the Dagster container under 1.5 GB total. Encoding 100K reviews in ~15 minutes is acceptable for a weekly batch job.

**Alternatives rejected**:
- `all-mpnet-base-v2`: 2x storage, 3x slower, marginal quality gain for this corpus size
- OpenAI embeddings API: Adds external dependency, recurring cost, network latency during batch processing
- Custom fine-tuned model: Premature -- insufficient labeled data for fine-tuning

**Status**: Accepted

### ADR-006: Review-Level Embeddings as the Foundation

**Context**: The requirements specify embedding each review, then averaging per book. An alternative is to embed concatenated review text directly, or to embed book descriptions only.

**Decision**: Store embeddings at the review level. Compute book embeddings as the mean of their review embeddings.

**Rationale**:
- Review-level embeddings are the atomic unit. They can be reused for future features (review-based search, similar-review discovery, critic taste profiling).
- Averaging at query time (or precomputing and caching) is more flexible than only storing the aggregate.
- Individual reviews capture different aspects of a book (prose style, themes, plot) that a single concatenated embedding would blur.
- Incremental: when a new review is added for a book, only the new review needs encoding. The book embedding is then recomputed cheaply (vector arithmetic, not model inference).

**Consequences**:
- Positive: Maximum flexibility, incremental updates, supports future features
- Negative: ~100K rows in review_embedding table vs ~13K for book-only approach. Additional storage (~150 MB for 100K x 384-dim vectors). Manageable at this scale.

**Status**: Accepted

### ADR-007: pgvector for Embedding Storage

**Context**: Need to store and query 384-dimensional vectors. Options: pgvector (in existing PostgreSQL), Redis with vector search, Pinecone, Qdrant, ChromaDB.

**Decision**: Use pgvector columns in the existing PostgreSQL instance.

**Rationale**:
- pgvector is already installed (the extension is created in `init_db()`)
- No additional infrastructure or services to manage
- Transactional consistency with relational data (book, review, user tables)
- Supports cosine distance, inner product, and L2 distance natively
- At 13K books and 100K reviews, pgvector performs well without HNSW indexing (exact search under 50ms)
- HNSW index can be added later if query latency exceeds 100ms

**Scaling note**: pgvector exact search degrades around 100K vectors. At that point, add:
```sql
CREATE INDEX ON review_embedding USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Status**: Accepted

### ADR-008: User Embedding via Signed-Weight Average

**Context**: Need to represent a user's taste as a single vector for nearest-neighbor search.

**Decision**: Compute user embedding as:

```
weight_i = rating_i - 2
user_embedding = sum(weight_i * book_embedding_i) / sum(|weight_i|)
```

This is a signed-weight centroid. Ratings map to weights as follows:

| Rating | Weight | Effect |
|--------|--------|--------|
| 1 star | -1 | Repels (pushes away from this book) |
| 2 stars | 0 | Neutral (ignored) |
| 3 stars | +1 | Mild attract |
| 4 stars | +2 | Attract |
| 5 stars | +3 | Strong attract |

Dividing by the sum of absolute weights keeps the embedding properly normalized regardless of the mix of positive and negative ratings.

**Trade-off analysis**:

| Approach | Pros | Cons |
|----------|------|------|
| Signed weight (rating - 2) | Repels from disliked books, preserves granularity, leverages negative signal | Requires at least one non-neutral rating. Users who rate everything 2 stars produce no signal. |
| Rating as weight | Simple, intuitive | Does not repel from disliked books; a 1-star book still attracts (weakly) |
| Binary (liked/disliked threshold) | Simplest | Loses rating granularity |

**Decision**: Implement signed-weight (rating - 2). This leverages the full range of user feedback, including negative signal from low ratings. Books rated 2 stars are neutral (zero weight) and do not contribute to the embedding. The offset of 2 (rather than 3) means a 3-star rating still contributes a mild positive signal, which is appropriate since a user bothering to rate a book 3/5 likely found it somewhat worthwhile.

**Status**: Accepted

### ADR-009: Precomputed vs. On-Demand Recommendations

**Context**: Should user embeddings and recommendation lists be computed at request time or precomputed in batch?

**Decision**: Hybrid approach.

- **Book embeddings**: Precomputed by Dagster asset, stored in database. Updated when new reviews are loaded.
- **User embeddings**: Computed on-demand at request time. A user with 10 ratings requires averaging 10 vectors (sub-millisecond). No precomputation needed.
- **Nearest-neighbor search**: Executed at request time via pgvector `ORDER BY embedding <=> query_vector`. For 13K books this is under 50ms.
- **Caching**: Add response-level caching (Redis or in-memory TTL cache) in Phase 5 if latency exceeds targets.

**Rationale**: At the current scale (13K books, sparse user ratings), on-demand computation is fast enough and avoids the complexity of cache invalidation when a user adds a new rating.

**Status**: Accepted

---

## 4. Database Schema Changes

### New Tables and Columns

Three changes to the database schema, all additive (no existing columns modified):

#### 4.1 Review Embedding Column

Add a `Vector(384)` column to the `Review` table.

```python
# In backend/db/models.py
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column

class Review(SQLModel, table=True):
    # ... existing fields ...
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(384)),
    )
```

#### 4.2 Book Embedding Column

Add a `Vector(384)` column to the `Book` table.

```python
class Book(SQLModel, table=True):
    # ... existing fields ...
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(384)),
    )
```

#### 4.3 Migration Strategy

Since the project uses `SQLModel.metadata.create_all()` (additive only, per `backend/database.py`), adding new nullable columns requires manual SQL migration:

```sql
-- Migration: add embedding columns
ALTER TABLE review ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE book ADD COLUMN IF NOT EXISTS embedding vector(384);

-- Index for nearest-neighbor search on book embeddings (defer until Phase 5 or >50K books)
-- CREATE INDEX idx_book_embedding_cosine ON book USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);
```

This migration should be executed in the backend `entrypoint.sh` or as part of the `init_db()` function in `backend/database.py`:

```python
def init_db() -> None:
    # ... existing create_all and vector extension ...
    with Session(engine) as session:
        session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Add embedding columns if they don't exist
        session.exec(text(
            "ALTER TABLE review ADD COLUMN IF NOT EXISTS embedding vector(384)"
        ))
        session.exec(text(
            "ALTER TABLE book ADD COLUMN IF NOT EXISTS embedding vector(384)"
        ))
        session.commit()
```

#### 4.4 No User Embedding Table

User embeddings are computed on-demand (see ADR-009). No new table or column needed for users. If precomputation becomes necessary in Phase 5, add:

```python
class UserEmbedding(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id', unique=True)
    embedding: list[float] = Field(sa_column=Column(Vector(384)))
    updated_at: datetime
```

---

## 5. Dagster Pipeline Integration

### Asset Graph Extension

The recommendation pipeline adds three new assets downstream of `load_books`:

```
[Existing Pipeline]
crawl_books -> raw_books -> validate_raw_books -> cleaned_books -> load_books
                                                                       |
                                                                       v
                                                              review_embeddings
                                                                       |
                                                                       v
                                                              book_embeddings
```

Both new assets belong to a new Dagster job: `embedding_pipeline`.

### New Files

```
src/litmatch/
  defs/
    assets/
      embedding.py              # review_embeddings + book_embeddings assets
    resources/
      embedding_model.py        # EmbeddingModelResource
```

### Asset: review_embeddings

**File**: `src/litmatch/defs/assets/embedding.py`

```python
import dagster as dg
from sqlmodel import Session, select, update
from backend.db.models import Review
from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.resources.embedding_model import EmbeddingModelResource


@dg.asset(
    deps=["load_books"],
    description="Generate embeddings for reviews that lack them",
    kinds={"python", "postgres", "ml"},
)
def review_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
    embedding_model: EmbeddingModelResource,
) -> None:
    """Encode review text into 384-dim vectors using sentence-transformers.

    Only processes reviews where embedding IS NULL (incremental).
    Encodes in batches of 256 for memory efficiency.
    """
    engine = database.get_engine()

    with Session(engine) as session:
        reviews = session.exec(
            select(Review).where(Review.embedding == None)
        ).all()

    if not reviews:
        context.log.info("All reviews already have embeddings")
        return

    context.log.info(f"Generating embeddings for {len(reviews)} reviews")

    batch_size = 256
    total_encoded = 0

    for i in range(0, len(reviews), batch_size):
        batch = reviews[i : i + batch_size]
        texts = [r.review for r in batch]
        embeddings = embedding_model.encode(texts)

        with Session(engine) as session:
            for review, emb in zip(batch, embeddings):
                session.exec(
                    update(Review)
                    .where(Review.id == review.id)
                    .values(embedding=emb)
                )
            session.commit()

        total_encoded += len(batch)
        context.log.info(f"Encoded {total_encoded}/{len(reviews)} reviews")

    context.log_event(
        dg.AssetMaterialization(
            asset_key="review_embeddings",
            metadata={
                "reviews_encoded": total_encoded,
                "model_name": embedding_model.model_name,
                "dimensions": embedding_model.dimensions,
            },
        )
    )
```

### Asset: book_embeddings

```python
import numpy as np
from backend.db.models import Book, Review


@dg.asset(
    deps=["review_embeddings"],
    description="Compute book embeddings by averaging review embeddings",
    kinds={"python", "postgres"},
)
def book_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
) -> None:
    """Average review embeddings per book to produce book-level embeddings.

    A book's embedding is the element-wise mean of all its review embeddings.
    Only recomputes for books where:
    - The book has no embedding yet, OR
    - The book has reviews with embeddings newer than the book's embedding

    Books with zero embedded reviews are skipped.
    """
    engine = database.get_engine()

    with Session(engine) as session:
        # Find books that have embedded reviews but no book embedding
        results = session.exec(
            select(Book.id)
            .join(Review, Review.book_id == Book.id)
            .where(Review.embedding != None)
            .where(Book.embedding == None)
            .distinct()
        ).all()

    if not results:
        context.log.info("All books already have embeddings")
        return

    context.log.info(f"Computing embeddings for {len(results)} books")
    computed = 0

    with Session(engine) as session:
        for book_id in results:
            reviews = session.exec(
                select(Review.embedding)
                .where(Review.book_id == book_id)
                .where(Review.embedding != None)
            ).all()

            if not reviews:
                continue

            # Element-wise mean of review embeddings
            avg_embedding = np.mean(
                [np.array(r) for r in reviews], axis=0
            ).tolist()

            session.exec(
                update(Book)
                .where(Book.id == book_id)
                .values(embedding=avg_embedding)
            )
            computed += 1

        session.commit()

    context.log.info(f"Computed {computed} book embeddings")

    context.log_event(
        dg.AssetMaterialization(
            asset_key="book_embeddings",
            metadata={
                "books_computed": computed,
            },
        )
    )
```

### Resource: EmbeddingModelResource

**File**: `src/litmatch/defs/resources/embedding_model.py`

```python
import dagster as dg


class EmbeddingModelResource(dg.ConfigurableResource):
    """Manages a sentence-transformers model for text encoding.

    The model is lazily loaded on first use and cached for the lifetime
    of the resource (i.e., the Dagster code server process).
    """

    model_name: str = "all-MiniLM-L6-v2"

    _model: object | None = None

    @property
    def dimensions(self) -> int:
        model_dimensions: dict[str, int] = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
        }
        return model_dimensions.get(self.model_name, 384)

    def _get_model(self) -> object:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
        return embeddings.tolist()
```

### Job and Definitions Update

**File**: `src/litmatch/defs/jobs.py`

```python
import dagster as dg

embedding_pipeline = dg.define_asset_job(
    name="embedding_pipeline",
    selection=dg.AssetSelection.assets("review_embeddings", "book_embeddings"),
    description="Generate review and book embeddings for the recommender system.",
)
```

**File**: `src/litmatch/definitions.py` -- add to the `defs()` function:

```python
import os
from litmatch.defs.assets.embedding import review_embeddings, book_embeddings
from litmatch.defs.jobs import embedding_pipeline
from litmatch.defs.resources.embedding_model import EmbeddingModelResource

# In the Definitions:
dg.Definitions(
    assets=[..., review_embeddings, book_embeddings],
    jobs=[..., embedding_pipeline],
    resources={
        ...,
        "embedding_model": EmbeddingModelResource(
            model_name=os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
        ),
    },
)
```

### Dockerfile.dagster Changes

The Dagster container at `Dockerfile.dagster` needs sentence-transformers and PyTorch (CPU-only):

```dockerfile
FROM python:3.12-slim

WORKDIR /opt/dagster/app

# System deps for psycopg2 and numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY backend/ ./backend/

# Install with CPU-only PyTorch to keep image size reasonable
RUN uv sync --frozen --no-dev

COPY dagster_home/dagster.yaml /opt/dagster/dagster_home/dagster.yaml
COPY workspace.yaml /opt/dagster/dagster_home/workspace.yaml

RUN mkdir -p /opt/dagster/dagster_home/storage

ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV PYTHONPATH=/opt/dagster/app

CMD ["uv", "run", "dagster", "code-server", "start", \
     "--host", "0.0.0.0", "--port", "4000", \
     "--module-name", "litmatch.definitions"]
```

The `pyproject.toml` dependencies need:

```toml
dependencies = [
    # ... existing ...
    "sentence-transformers>=3.0.0",
    "torch>=2.0.0",
    "numpy>=1.26.0",
]
```

**Image size impact**: The Dagster container will grow from ~500 MB to ~1.5 GB due to PyTorch CPU. This is acceptable for a single-machine deployment.

---

## 6. API Endpoint Design

### 6.1 GET /recommendations/

**Authentication**: Required (Bearer token)

**Purpose**: Return personalized book recommendations for the authenticated user, separated by fiction and non-fiction.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int (1-50) | 10 | Max recommendations per category |
| `category` | "fiction" \| "nonfiction" \| "all" | "all" | Filter by fiction/non-fiction |

**Response Shape**:

```typescript
interface RecommendationResponse {
  fiction: BookRead[];
  nonfiction: BookRead[];
  meta: {
    user_ratings_count: number;
    min_ratings_required: number;
    strategy: "personalized" | "popular";
  };
}
```

**Algorithm (pseudocode)**:

```
1. Fetch all UserRating rows for current user
2. If count < MIN_RATINGS (5):
     Return popular books (by avg critic rating), separated by is_fiction
     Set strategy = "popular"
3. Else:
     Fetch book embeddings for rated books
     Compute user_embedding = signed_weight_average(book_embeddings, ratings)
       where weight_i = rating_i - 2 (ratings of 2 are neutral, <2 repels, >2 attracts)
     Query pgvector: nearest books to user_embedding WHERE book.id NOT IN rated_book_ids
     Split results by is_fiction
     Set strategy = "personalized"
4. Return response
```

**Implementation sketch** (to be added to `backend/app/main.py`):

```python
from typing import Literal
from fastapi import Query, Depends
from backend.app.recommendations import (
    compute_user_embedding,
    find_nearest_books,
    get_popular_books,
)


@app.get("/recommendations/", response_model=RecommendationResponse)
def get_recommendations(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
    category: Literal["fiction", "nonfiction", "all"] = "all",
):
    MIN_RATINGS = 5

    # Get user's ratings
    user_ratings = session.exec(
        select(UserRating).where(UserRating.user_id == current_user.id)
    ).all()

    rated_book_ids = [r.book_id for r in user_ratings]

    if len(user_ratings) < MIN_RATINGS:
        return _popular_recommendations(session, rated_book_ids, limit, category)

    return _personalized_recommendations(
        session, user_ratings, rated_book_ids, limit, category
    )


def _popular_recommendations(
    session: Session,
    exclude_book_ids: list[int],
    limit: int,
    category: str,
) -> RecommendationResponse:
    """Return popular books when user has insufficient ratings."""
    fiction = []
    nonfiction = []

    if category in ("fiction", "all"):
        fiction = get_popular_books(
            session, exclude_book_ids, is_fiction=True, limit=limit
        )

    if category in ("nonfiction", "all"):
        nonfiction = get_popular_books(
            session, exclude_book_ids, is_fiction=False, limit=limit
        )

    return RecommendationResponse(
        fiction=fiction,
        nonfiction=nonfiction,
        meta=RecommendationMeta(
            user_ratings_count=len(exclude_book_ids),
            min_ratings_required=5,
            strategy="popular",
        ),
    )


def _personalized_recommendations(
    session: Session,
    user_ratings: list[UserRating],
    exclude_book_ids: list[int],
    limit: int,
    category: str,
) -> RecommendationResponse:
    """Return personalized recommendations via nearest-neighbor search."""
    user_embedding = compute_user_embedding(session, user_ratings)

    if not user_embedding:
        # Fallback if rated books have no embeddings yet
        return _popular_recommendations(session, exclude_book_ids, limit, category)

    fiction = []
    nonfiction = []

    if category in ("fiction", "all"):
        fiction = find_nearest_books(
            session, user_embedding, exclude_book_ids, is_fiction=True, limit=limit
        )

    if category in ("nonfiction", "all"):
        nonfiction = find_nearest_books(
            session, user_embedding, exclude_book_ids, is_fiction=False, limit=limit
        )

    return RecommendationResponse(
        fiction=fiction,
        nonfiction=nonfiction,
        meta=RecommendationMeta(
            user_ratings_count=len(user_ratings),
            min_ratings_required=5,
            strategy="personalized",
        ),
    )
```

### 6.2 GET /books/semantic-search

**Authentication**: Not required

**Purpose**: Search books using natural language (semantic similarity via embeddings).

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | str (2-500 chars) | required | Natural language query |
| `page` | int (>= 1) | 1 | Page number |
| `limit` | int (1-100) | 24 | Results per page |

**Response Shape**: `PaginatedResponse[BookRead]` (same as existing search)

**Implementation**: Encode query with the same sentence-transformers model (loaded once at backend startup), query pgvector with cosine distance ordering.

**Critical design decision**: The sentence-transformers model must be loaded ONCE at FastAPI startup, not per-request. Add to `backend/app/main.py`:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def _get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


@app.get("/books/semantic-search", response_model=PaginatedResponse[BookRead])
def semantic_search(
    *,
    session: Session = Depends(get_session),
    q: str = Query(..., min_length=2, max_length=500),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
):
    """Search books using semantic similarity on embeddings."""
    model = _get_embedding_model()
    query_embedding = model.encode([q])[0].tolist()

    offset = (page - 1) * limit

    books = session.exec(
        select(Book)
        .where(Book.embedding != None)
        .order_by(Book.embedding.cosine_distance(query_embedding))
        .offset(offset)
        .limit(limit)
    ).all()

    # Count total for pagination
    total = session.exec(
        select(func.count(Book.id)).where(Book.embedding != None)
    ).one()

    return PaginatedResponse(
        items=books,
        total=total,
        page=page,
        limit=limit,
    )
```

**Backend Dockerfile impact**: The backend container at `backend/Dockerfile` also needs sentence-transformers for the semantic search and recommendation endpoints. This adds ~1 GB to the backend image.

### 6.3 GET /users/me

**Authentication**: Required

**Purpose**: Return current user's profile data for the frontend profile page.

```python
@app.get("/users/me", response_model=UserProfile)
def get_current_user_profile(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rating_count = session.exec(
        select(func.count(UserRating.id))
        .where(UserRating.user_id == current_user.id)
    ).one()

    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        total_ratings=rating_count,
    )
```

### 6.4 Response Models

Add to `backend/db/models.py`:

```python
from typing import Literal
from pydantic import BaseModel


class UserProfile(BaseModel):
    id: int
    username: str
    total_ratings: int
    model_config = {"from_attributes": True}


class RecommendationMeta(BaseModel):
    user_ratings_count: int
    min_ratings_required: int
    strategy: Literal["personalized", "popular"]


class RecommendationResponse(BaseModel):
    fiction: list[BookRead]
    nonfiction: list[BookRead]
    meta: RecommendationMeta
```

---

## 7. Backend Recommendation Logic

### Recommendation Module

**File**: `backend/app/recommendations.py`

```python
"""Recommendation logic for LitMatch.

Computes user taste embeddings and finds nearest books via pgvector.
"""
import numpy as np
from sqlmodel import Session, select, func
from backend.db.models import Book, UserRating


MIN_RATINGS = 5


def compute_user_embedding(
    session: Session,
    user_ratings: list[UserRating],
) -> list[float] | None:
    """Compute a user's taste embedding as a signed-weight average of book embeddings.

    Weight = rating - 2, so:
      1 star -> -1 (repels), 2 stars -> 0 (neutral, skipped),
      3 stars -> +1, 4 stars -> +2, 5 stars -> +3 (attracts).

    Normalizes by sum of absolute weights to keep the embedding unit-scaled.

    Args:
        session: Active database session.
        user_ratings: The user's ratings with book_id and rating fields.

    Returns:
        384-dim embedding vector, or None if no rated books have embeddings
        or all ratings are neutral (2 stars).
    """
    book_ids = [r.book_id for r in user_ratings]
    rating_map = {r.book_id: r.rating for r in user_ratings}

    books = session.exec(
        select(Book).where(Book.id.in_(book_ids)).where(Book.embedding != None)
    ).all()

    if not books:
        return None

    weighted_sum = np.zeros(384)
    abs_weight_total = 0.0

    for book in books:
        weight = float(rating_map[book.id]) - 2.0
        if weight == 0:
            continue  # 2-star ratings are neutral
        weighted_sum += weight * np.array(book.embedding)
        abs_weight_total += abs(weight)

    if abs_weight_total == 0:
        return None

    return (weighted_sum / abs_weight_total).tolist()


def find_nearest_books(
    session: Session,
    user_embedding: list[float],
    exclude_book_ids: list[int],
    is_fiction: bool | None,
    limit: int,
) -> list[Book]:
    """Find books nearest to the user embedding via pgvector cosine distance.

    Args:
        session: Active database session.
        user_embedding: The user's taste embedding.
        exclude_book_ids: Book IDs to exclude (already rated).
        is_fiction: Filter by fiction (True), non-fiction (False), or all (None).
        limit: Maximum number of results.

    Returns:
        List of Book objects ordered by similarity.
    """
    stmt = (
        select(Book)
        .where(Book.embedding != None)
        .where(Book.id.notin_(exclude_book_ids))
        .order_by(Book.embedding.cosine_distance(user_embedding))
        .limit(limit)
    )

    if is_fiction is not None:
        stmt = stmt.where(Book.is_fiction == is_fiction)

    return list(session.exec(stmt).all())


def get_popular_books(
    session: Session,
    exclude_book_ids: list[int],
    is_fiction: bool | None,
    limit: int,
) -> list[Book]:
    """Get popular books by average critic rating (fallback for cold-start).

    Args:
        session: Active database session.
        exclude_book_ids: Book IDs to exclude (already rated).
        is_fiction: Filter by fiction (True), non-fiction (False), or all (None).
        limit: Maximum number of results.

    Returns:
        List of Book objects ordered by critic rating.
    """
    stmt = (
        select(Book)
        .where(Book.id.notin_(exclude_book_ids))
        .order_by(Book.critic_rating.desc())
        .limit(limit)
    )

    if is_fiction is not None:
        stmt = stmt.where(Book.is_fiction == is_fiction)

    return list(session.exec(stmt).all())
```

---

## 8. Implementation Phases

### Phase 1: Review Embeddings

**Goal**: Generate and store 384-dim embeddings for all review texts.

**Duration estimate**: 2-3 days

| Step | Description | Files |
|------|-------------|-------|
| 1.1 | Add `embedding` Vector(384) column to Review model | `backend/db/models.py` |
| 1.2 | Add migration SQL to `init_db()` | `backend/database.py` |
| 1.3 | Add `sentence-transformers`, `torch`, `numpy` to pyproject.toml | `pyproject.toml` |
| 1.4 | Create `EmbeddingModelResource` | `src/litmatch/defs/resources/embedding_model.py` |
| 1.5 | Create `review_embeddings` asset | `src/litmatch/defs/assets/embedding.py` |
| 1.6 | Register resource and asset in definitions.py | `src/litmatch/definitions.py` |
| 1.7 | Update `Dockerfile.dagster` for torch dependencies | `Dockerfile.dagster` |
| 1.8 | Write unit tests for EmbeddingModelResource (mocked model) | `tests/dagster/test_embedding.py` |
| 1.9 | Write integration test: materialize review_embeddings against test DB | `tests/integration/test_embeddings.py` |

**Success criteria**:
- `review_embeddings` asset materializes, encoding all reviews without embeddings
- Re-running the asset is a no-op (idempotent via `WHERE embedding IS NULL`)
- Dagster UI shows metadata: `reviews_encoded`, `model_name`, `dimensions`
- Unit tests pass with mocked sentence-transformers model
- Container builds successfully with sentence-transformers

### Phase 2: Book Embeddings

**Goal**: Compute per-book embeddings as the mean of review embeddings.

**Duration estimate**: 1-2 days

| Step | Description | Files |
|------|-------------|-------|
| 2.1 | Add `embedding` Vector(384) column to Book model | `backend/db/models.py` |
| 2.2 | Add migration SQL for book embedding column | `backend/database.py` |
| 2.3 | Create `book_embeddings` asset | `src/litmatch/defs/assets/embedding.py` (same file) |
| 2.4 | Create `embedding_pipeline` job | `src/litmatch/defs/jobs.py` |
| 2.5 | Register in definitions.py | `src/litmatch/definitions.py` |
| 2.6 | Write unit tests for averaging logic | `tests/dagster/test_embedding.py` |
| 2.7 | Write integration test: full embedding pipeline | `tests/integration/test_embeddings.py` |

**Success criteria**:
- `book_embeddings` asset computes averages for all books with embedded reviews
- Books without any reviews (or reviews without embeddings) are skipped
- Re-running is idempotent
- The full `embedding_pipeline` job (review_embeddings -> book_embeddings) completes

### Phase 3: User Embeddings + Recommendation API

**Goal**: Serve personalized recommendations via FastAPI.

**Duration estimate**: 3-4 days

| Step | Description | Files |
|------|-------------|-------|
| 3.1 | Add `RecommendationResponse`, `UserProfile` models | `backend/db/models.py` |
| 3.2 | Implement `compute_user_embedding()` helper | `backend/app/recommendations.py` (new) |
| 3.3 | Implement `get_popular_books()` fallback | `backend/app/recommendations.py` |
| 3.4 | Implement `find_nearest_books()` | `backend/app/recommendations.py` |
| 3.5 | Add `GET /recommendations/` endpoint | `backend/app/main.py` |
| 3.6 | Add `GET /users/me` endpoint | `backend/app/main.py` |
| 3.7 | Add sentence-transformers to pyproject.toml | `pyproject.toml` |
| 3.8 | Update backend Dockerfile for torch | `backend/Dockerfile` |
| 3.9 | Write unit tests for user embedding computation | `backend/tests/test_recommendations.py` (new) |
| 3.10 | Write unit tests for fallback logic | `backend/tests/test_recommendations.py` |
| 3.11 | Write integration test for /recommendations/ endpoint | `tests/integration/test_backend_api.py` |

**Success criteria**:
- `GET /recommendations/` returns fiction and nonfiction arrays
- Users with < 5 ratings get popular books (fallback)
- Users with >= 5 ratings get personalized nearest-neighbor results
- Response includes `meta.strategy` field
- Already-rated books are excluded from results
- Endpoint requires authentication (401 without token)

### Phase 4: Fiction/Non-Fiction Separation + Frontend

**Goal**: Frontend displays recommendations separated by category.

**Duration estimate**: 2-3 days

| Step | Description | Files |
|------|-------------|-------|
| 4.1 | Add `useRecommendations` hook | `frontend/src/hooks/useRecommendations.ts` |
| 4.2 | Create ProfilePage with "My Ratings" + "Recommended" sections | `frontend/src/pages/ProfilePage.tsx` |
| 4.3 | Add fiction/nonfiction tabs in recommendation section | `frontend/src/pages/ProfilePage.tsx` |
| 4.4 | Add `/profile` route (protected) | `frontend/src/App.tsx` |
| 4.5 | Add "Recommended" link in authenticated header | `frontend/src/components/Header.tsx` |
| 4.6 | Write component tests | `frontend/src/pages/ProfilePage.test.tsx` |
| 4.7 | Write hook tests | `frontend/src/hooks/useRecommendations.test.ts` |

**Frontend hook** (`frontend/src/hooks/useRecommendations.ts`):

```typescript
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

interface RecommendationMeta {
  user_ratings_count: number;
  min_ratings_required: number;
  strategy: "personalized" | "popular";
}

interface RecommendationResponse {
  fiction: BookRead[];
  nonfiction: BookRead[];
  meta: RecommendationMeta;
}

export function useRecommendations(limit = 10) {
  return useQuery<RecommendationResponse>({
    queryKey: ["recommendations", limit],
    queryFn: async () => {
      const { data } = await api.get("/recommendations/", {
        params: { limit },
      });
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
```

**Success criteria**:
- Profile page shows rated books grid and recommendation grid
- Recommendations are separated into Fiction and Non-Fiction tabs
- Empty states: "Rate more books" when < 5 ratings
- "Recommended for You" strategy label (personalized vs popular)

### Phase 5: Semantic Search + Optimization

**Goal**: Add semantic search endpoint, optimize performance, add caching.

**Duration estimate**: 3-4 days

| Step | Description | Files |
|------|-------------|-------|
| 5.1 | Load sentence-transformers model at FastAPI startup | `backend/app/main.py` |
| 5.2 | Implement `GET /books/semantic-search` endpoint | `backend/app/main.py` |
| 5.3 | Add HNSW index on book.embedding (if >10K books) | Migration SQL |
| 5.4 | Add response caching for recommendations (TTL 5 min) | `backend/app/recommendations.py` |
| 5.5 | Add embedding recomputation sensor (trigger on new reviews) | `src/litmatch/defs/sensors/embedding_sensor.py` |
| 5.6 | Write semantic search tests | `backend/tests/test_search.py` |
| 5.7 | Write integration tests | `tests/integration/test_backend_api.py` |
| 5.8 | Update frontend SearchBar to offer semantic search toggle | `frontend/src/components/SearchBar.tsx` |

---

## 9. Performance Considerations

### Embedding Generation (Batch -- Dagster)

| Metric | Target | Approach |
|--------|--------|----------|
| Initial encoding (100K reviews) | < 20 minutes | Batch encoding with batch_size=64 in sentence-transformers |
| Incremental encoding (new reviews) | < 1 minute | `WHERE embedding IS NULL` filter |
| Book embedding recomputation | < 30 seconds | Vector arithmetic, no model inference |
| Memory usage during encoding | < 2 GB | Process in batches of 256, commit after each batch |

### Recommendation Serving (Request -- FastAPI)

| Metric | Target | Approach |
|--------|--------|----------|
| User embedding computation | < 5 ms | Average 5-50 vectors (numpy in-memory) |
| Nearest-neighbor search (13K books) | < 50 ms | pgvector exact search (no index needed at this scale) |
| Total endpoint latency | < 100 ms | On-demand computation, no precomputation needed |
| Semantic search (query encoding) | < 200 ms | Model cached at startup, single-text encoding |

### Storage

| Item | Size Estimate |
|------|---------------|
| Review embeddings (100K x 384 dim) | ~150 MB |
| Book embeddings (13K x 384 dim) | ~20 MB |
| HNSW index (if added) | ~50 MB |
| Total pgvector overhead | ~220 MB |

### Scaling Thresholds

| Threshold | Action Required |
|-----------|----------------|
| > 50K books | Add HNSW index on book.embedding |
| > 500K reviews | Partition embedding generation by batch, add checkpointing |
| > 10K concurrent users | Add Redis cache for recommendation responses |
| > 100K books | Evaluate approximate nearest neighbor (ANN) with HNSW tuning (ef_search parameter) |
| > 1M books | Consider dedicated vector database (Qdrant, Weaviate) |

---

## 10. Testing Strategy

### Unit Tests

| Test File | What It Tests |
|-----------|---------------|
| `tests/dagster/test_embedding.py` | EmbeddingModelResource (mocked model), review_embeddings asset logic, book_embeddings averaging logic, incremental behavior (skip already-embedded) |
| `backend/tests/test_recommendations.py` | `compute_user_embedding()` with various rating distributions (verifying signed-weight: negative ratings repel, neutral ratings ignored, positive ratings attract), `find_nearest_books()` with fiction/nonfiction filters, fallback logic when < MIN_RATINGS, edge cases (no embeddings, no rated books, all-neutral ratings) |

### Integration Tests

| Test File | What It Tests |
|-----------|---------------|
| `tests/integration/test_embeddings.py` | Full embedding pipeline against test database: insert test books/reviews, materialize review_embeddings + book_embeddings, verify vectors stored correctly |
| `tests/integration/test_backend_api.py` (extended) | `GET /recommendations/` with test user who has rated books with embeddings, fiction/nonfiction separation, fallback for new users, auth requirement |

### Test Fixtures

The existing test fixture at `tests/integration/fixtures/books.jsonl` contains 3 sample books. Extend with:
- At least 2 fiction and 2 non-fiction books with reviews
- Pre-computed mock embeddings (fixed vectors) for deterministic nearest-neighbor testing
- A test user with 6+ ratings spanning both fiction and non-fiction

### Mocking Strategy for Unit Tests

The sentence-transformers model is expensive to load. All unit tests must mock it:

```python
@pytest.fixture
def mock_embedding_model(monkeypatch):
    """Return a fixed embedding for any text input."""
    import numpy as np

    class FakeModel:
        def encode(self, texts, **kwargs):
            return np.random.RandomState(42).rand(len(texts), 384)

    monkeypatch.setattr(
        "sentence_transformers.SentenceTransformer",
        lambda name: FakeModel(),
    )
```

### Coverage Targets

| Module | Target |
|--------|--------|
| `defs/resources/embedding_model.py` | 90% |
| `defs/assets/embedding.py` | 85% |
| `backend/app/recommendations.py` | 90% |
| `/recommendations/` endpoint | 85% |
| Frontend hooks + components | 80% |

---

## 11. Integration Points Summary

### How Each Component Connects

```
                     Dagster ETL Pipeline
                            |
                   [load_books asset]
                            |
                            v
                  [review_embeddings asset]
                    (sentence-transformers)
                            |
                            v
                  [book_embeddings asset]
                    (numpy averaging)
                            |
                            v
                    PostgreSQL + pgvector
                   /         |         \
                  /          |          \
    Book.embedding  Review.embedding  UserRating
                  \          |          /
                   \         |         /
                    FastAPI Backend
                   /                \
    GET /recommendations/    GET /books/semantic-search
         (pgvector cosine)        (pgvector cosine)
                   \                /
                    React Frontend
                   /                \
          ProfilePage          SearchBar (semantic)
     (fiction/nonfiction tabs)
```

### Environment Variables (New)

| Variable | Required | Default | Used By |
|----------|----------|---------|---------|
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | Dagster, Backend |
| `MIN_RATINGS_FOR_RECS` | No | `5` | Backend |

### Container Changes

| Container | Change |
|-----------|--------|
| `dagster-code` | Add sentence-transformers + torch to image (+~1 GB) |
| `dagster-daemon` | Same image as dagster-code (no change) |
| `backend` | Add sentence-transformers + torch to image (+~1 GB) for semantic search |
| `db` | No change (pgvector already installed) |
| `frontend` | New ProfilePage, useRecommendations hook |

---

## 12. Risk Assessment and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Container image too large (>2 GB) | Medium | Medium | Use PyTorch CPU-only wheels, multi-stage Docker build, `.dockerignore` for test files |
| Cold start (no user ratings) | High | Medium | Popular-books fallback, minimum rating threshold, prompt users to rate |
| Poor recommendation quality | Medium | High | Validate with manual inspection of nearest-neighbor results, A/B test against popular-books baseline |
| Review text too short for meaningful embeddings | Low | Medium | Review texts are professional critic reviews (100-500 words), rich enough for sentence-transformers |
| pgvector query latency at scale | Low | Medium | Exact search is fast for 13K books. Add HNSW index proactively at 50K+ |
| Embedding model updates break compatibility | Low | High | Store `model_name` and `dimensions` as metadata. If model changes, recompute all embeddings (flag via NULL). |
| Memory pressure during batch encoding | Medium | Low | Batch size of 256 keeps peak memory under 2 GB. Commit after each batch. |

---

## 13. What This Replaces

The existing recommender at `recommender/recommender.py`:
- Uses surprise library SVD on critic reviews (treating critics as "users")
- Reads from a manually exported CSV file
- Is completely standalone with no database or API integration
- Has a pinned `numpy<2` dependency that conflicts with modern sentence-transformers

**Disposition**: The `recommender/` directory should be archived (moved to `archive/` or deleted) once Phase 3 is complete. The SVD approach is superseded by the embedding-based approach which:
1. Uses actual user ratings (not critic-as-user proxy)
2. Leverages semantic content understanding (not just rating patterns)
3. Is fully integrated into the Dagster pipeline and FastAPI backend
4. Handles cold-start gracefully (popular-books fallback)

---

## 14. Open Questions

These should be resolved before or during implementation:

1. **Should the recommendation endpoint also return a similarity score?** A cosine distance could be normalized to a 0-100 "match %" for the UI. Adds minimal complexity.

2. **Should books with `is_fiction IS NULL` be included in both fiction and nonfiction results, or excluded?** Currently some books lack fiction classification. Recommend: include in both categories until classification coverage improves.

3. **Should the embedding pipeline run automatically after every ETL load, or on a separate schedule?** Recommend: chain it to `load_books` via Dagster dependency (already designed this way). No separate schedule needed.

4. **What is the minimum number of embedded reviews a book needs to have a meaningful embedding?** A book with 1 review gets that review's embedding directly. A book with 10 reviews gets a richer average. Recommend: require at least 1 review (no minimum threshold beyond existence).

5. ~~**Should negative ratings (1-2 stars) reduce a book's contribution to the user embedding, or should they be excluded entirely?**~~ **Resolved**: The signed-weight approach (rating - 2) handles this naturally. A 1-star rating contributes weight -1, actively repelling the user embedding from that book's direction. A 2-star rating is neutral (weight 0) and ignored. Ratings of 3+ attract.

---

## 15. Summary

This roadmap provides a complete architectural specification for the LitMatch recommender system MVP. The five-phase implementation plan delivers incremental value:

- **Phase 1-2**: Embedding infrastructure (Dagster pipeline, database schema)
- **Phase 3**: User-facing recommendations API
- **Phase 4**: Frontend integration with fiction/non-fiction separation
- **Phase 5**: Performance optimization and semantic search

The design prioritizes:
- **Simplicity**: CPU-friendly models, on-demand computation, no external services
- **Flexibility**: Review-level embeddings support future features
- **Scalability**: Clear thresholds and upgrade paths as data grows
- **Quality**: Professional critic reviews provide rich semantic signal

Total estimated implementation time: **11-16 days** across all phases.
