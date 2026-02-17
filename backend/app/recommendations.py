"""Recommendation engine for LitMatch.

Computes user taste embeddings from rated book embeddings and finds
nearest books using pgvector cosine distance.
"""
from collections import Counter
from typing import Literal

from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from backend.app.queries import build_rating_subquery
from backend.db.models import Book, BookEmbedding, BookGenreLink, Review, UserRating

MIN_RATINGS = 5
CategoryFilter = Literal["fiction", "nonfiction", "all"]


def _compute_weighted_embedding(
    ratings_with_embeddings: list[tuple[int, list[float] | None]],
) -> list[float] | None:
    """Compute signed-weight average embedding from (rating, embedding) pairs.

    Weight formula: weight = rating - 2
      1-star -> -1, 2-star -> 0, 3-star -> +1, 4-star -> +2, 5-star -> +3

    Normalizes by sum of absolute weights.

    Returns None if all weights are zero, all embeddings are None,
    or input is empty.
    """
    weighted_pairs: list[tuple[int, list[float]]] = []
    for rating, embedding in ratings_with_embeddings:
        if embedding is None:
            continue
        weight = rating - 2
        if weight == 0:
            continue
        weighted_pairs.append((weight, embedding))

    if not weighted_pairs:
        return None

    # Validate all embeddings have consistent dimensions.  During the migration
    # transition period, composite (1152-dim) and review (384-dim) embeddings
    # may be mixed.  Filter to the majority dimension to prevent IndexError and
    # silent dimension corruption.
    dim = len(weighted_pairs[0][1])
    mismatched = [i for i, (_, e) in enumerate(weighted_pairs) if len(e) != dim]
    if mismatched:
        dim_counts: Counter[int] = Counter(len(e) for _, e in weighted_pairs)
        majority_dim = dim_counts.most_common(1)[0][0]
        weighted_pairs = [(w, e) for w, e in weighted_pairs if len(e) == majority_dim]
        dim = majority_dim

    if not weighted_pairs:
        return None

    result = [0.0] * dim
    abs_weight_sum = 0.0

    for weight, embedding in weighted_pairs:
        abs_weight_sum += abs(weight)
        for i in range(dim):
            result[i] += weight * embedding[i]

    return [v / abs_weight_sum for v in result]


def compute_user_embedding(
    session: Session,
    user_id: int,
    category: CategoryFilter = "all",
) -> list[float] | None:
    """Fetch user's ratings with book embeddings and compute weighted average.

    When *category* is ``"fiction"`` or ``"nonfiction"``, only ratings for
    books matching that category are included so the embedding reflects the
    user's taste within the requested category.

    Args:
        session: Active database session.
        user_id: The user whose embedding to compute.
        category: Restrict to ``"fiction"``, ``"nonfiction"``, or ``"all"``.

    Returns:
        1152-dim embedding vector (or 384-dim if only review_embedding exists),
        or None if no rated books have embeddings or all ratings are neutral (2 stars).
    """
    stmt = (
        select(UserRating.rating, BookEmbedding.embedding, BookEmbedding.review_embedding)
        .join(Book, UserRating.book_id == Book.id)
        .join(BookEmbedding, Book.id == BookEmbedding.book_id)
        .where(UserRating.user_id == user_id)
    )

    if category == "fiction":
        stmt = stmt.where(Book.is_fiction == True)  # noqa: E712
    elif category == "nonfiction":
        stmt = stmt.where(Book.is_fiction == False)  # noqa: E712

    rows = session.exec(stmt).all()

    # Use composite embedding if available, otherwise fall back to review_embedding
    ratings_with_embeddings = [
        (r.rating, r.embedding if r.embedding is not None else r.review_embedding)
        for r in rows
    ]
    return _compute_weighted_embedding(ratings_with_embeddings)


def get_popular_books(
    session: Session,
    exclude_book_ids: set[int],
    category: CategoryFilter = "all",
    limit: int = 20,
    genre_id: int | None = None,
    offset: int = 0,
) -> tuple[list[Book], int]:
    """Return top-rated books by average critic (Review) rating.

    Falls back strategy for users with fewer than MIN_RATINGS ratings.
    Excludes books the user has already rated.

    Args:
        session: Active database session.
        exclude_book_ids: Book IDs to exclude (already rated).
        category: Filter by "fiction", "nonfiction", or "all".
        limit: Maximum number of results.
        genre_id: Optional genre ID to filter results.
        offset: Number of results to skip.

    Returns:
        Tuple of (list of Book objects ordered by average critic rating
        descending, total count of matching books).
    """
    rating_sub = build_rating_subquery()

    base_stmt = select(Book).join(rating_sub, Book.id == rating_sub.c.book_id)

    if exclude_book_ids:
        base_stmt = base_stmt.where(Book.id.notin_(exclude_book_ids))

    if category == "fiction":
        base_stmt = base_stmt.where(Book.is_fiction == True)  # noqa: E712
    elif category == "nonfiction":
        base_stmt = base_stmt.where(Book.is_fiction == False)  # noqa: E712

    if genre_id is not None:
        base_stmt = base_stmt.join(
            BookGenreLink, Book.id == BookGenreLink.book_id
        ).where(BookGenreLink.genre_id == genre_id)

    # Count total matching books
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = session.exec(count_stmt).one()

    # Fetch paginated results
    fetch_stmt = (
        base_stmt.options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .order_by(
            rating_sub.c.avg_rating.desc().nulls_last(),
            rating_sub.c.review_count.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(session.exec(fetch_stmt).all()), total


def find_nearest_books(
    session: Session,
    user_embedding: list[float],
    exclude_book_ids: set[int],
    category: CategoryFilter = "all",
    limit: int = 20,
    genre_id: int | None = None,
    offset: int = 0,
) -> tuple[list[Book], int]:
    """Find nearest books by cosine distance using pgvector.

    Uses pgvector's cosine_distance operator on BookEmbedding.embedding.
    Falls back to popular books if no books have composite embeddings yet.
    Excludes specified book IDs and optionally filters by category and genre.

    Args:
        session: Active database session.
        user_embedding: The user's taste embedding (384 or 1152 dimensions).
        exclude_book_ids: Book IDs to exclude (already rated).
        category: Filter by "fiction", "nonfiction", or "all".
        limit: Maximum number of results.
        genre_id: Optional genre ID to filter results.
        offset: Number of results to skip.

    Returns:
        Tuple of (list of Book objects ordered by cosine similarity,
        total count of matching books).
    """
    # Build base query joining with book_embeddings
    base_stmt = (
        select(Book)
        .join(BookEmbedding, Book.id == BookEmbedding.book_id)
    )

    # Determine which embedding column to use based on user_embedding dimensions
    user_dim = len(user_embedding)
    if user_dim == 1152:
        # Use composite embedding if available, otherwise filter out
        embedding_col = BookEmbedding.embedding
        base_stmt = base_stmt.where(BookEmbedding.embedding.isnot(None))
    else:
        # Use review_embedding for backward compatibility (384 dimensions)
        embedding_col = BookEmbedding.review_embedding
        base_stmt = base_stmt.where(BookEmbedding.review_embedding.isnot(None))

    if exclude_book_ids:
        base_stmt = base_stmt.where(Book.id.notin_(exclude_book_ids))

    if category == "fiction":
        base_stmt = base_stmt.where(Book.is_fiction == True)  # noqa: E712
    elif category == "nonfiction":
        base_stmt = base_stmt.where(Book.is_fiction == False)  # noqa: E712

    if genre_id is not None:
        base_stmt = base_stmt.join(
            BookGenreLink, Book.id == BookGenreLink.book_id
        ).where(BookGenreLink.genre_id == genre_id)

    # Count total matching books
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = session.exec(count_stmt).one()

    # If no books have embeddings, fall back to popular books
    if total == 0:
        return get_popular_books(
            session, exclude_book_ids, category, limit, genre_id, offset
        )

    # Fetch paginated results
    fetch_stmt = (
        base_stmt.options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .order_by(embedding_col.cosine_distance(user_embedding))
        .offset(offset)
        .limit(limit)
    )

    return list(session.exec(fetch_stmt).all()), total
