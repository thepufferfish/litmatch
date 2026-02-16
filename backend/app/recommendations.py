"""Recommendation engine for LitMatch.

Computes user taste embeddings from rated book embeddings and finds
nearest books using pgvector cosine distance.
"""
from typing import Literal

from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from backend.app.queries import build_rating_subquery
from backend.db.models import Book, BookGenreLink, Review, UserRating

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

    dim = len(weighted_pairs[0][1])
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
        384-dim embedding vector, or None if no rated books have embeddings
        or all ratings are neutral (2 stars).
    """
    stmt = (
        select(UserRating.rating, Book.embedding)
        .join(Book, UserRating.book_id == Book.id)
        .where(UserRating.user_id == user_id)
    )

    if category == "fiction":
        stmt = stmt.where(Book.is_fiction == True)  # noqa: E712
    elif category == "nonfiction":
        stmt = stmt.where(Book.is_fiction == False)  # noqa: E712

    rows = session.exec(stmt).all()

    ratings_with_embeddings = [(r.rating, r.embedding) for r in rows]
    return _compute_weighted_embedding(ratings_with_embeddings)


def get_popular_books(
    session: Session,
    exclude_book_ids: set[int],
    category: CategoryFilter = "all",
    limit: int = 20,
    genre_id: int | None = None,
) -> list[Book]:
    """Return top-rated books by average critic (Review) rating.

    Falls back strategy for users with fewer than MIN_RATINGS ratings.
    Excludes books the user has already rated.

    Args:
        session: Active database session.
        exclude_book_ids: Book IDs to exclude (already rated).
        category: Filter by "fiction", "nonfiction", or "all".
        limit: Maximum number of results.
        genre_id: Optional genre ID to filter results.

    Returns:
        List of Book objects ordered by average critic rating descending.
    """
    rating_sub = build_rating_subquery()

    stmt = (
        select(Book)
        .options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .join(rating_sub, Book.id == rating_sub.c.book_id)
    )

    if exclude_book_ids:
        stmt = stmt.where(Book.id.notin_(exclude_book_ids))

    if category == "fiction":
        stmt = stmt.where(Book.is_fiction == True)  # noqa: E712
    elif category == "nonfiction":
        stmt = stmt.where(Book.is_fiction == False)  # noqa: E712

    if genre_id is not None:
        stmt = stmt.join(BookGenreLink, Book.id == BookGenreLink.book_id).where(
            BookGenreLink.genre_id == genre_id
        )

    stmt = stmt.order_by(
        rating_sub.c.avg_rating.desc().nulls_last(),
        rating_sub.c.review_count.desc(),
    ).limit(limit)

    return list(session.exec(stmt).all())


def find_nearest_books(
    session: Session,
    user_embedding: list[float],
    exclude_book_ids: set[int],
    category: CategoryFilter = "all",
    limit: int = 20,
    genre_id: int | None = None,
) -> list[Book]:
    """Find nearest books by cosine distance using pgvector.

    Uses pgvector's cosine_distance operator on Book.embedding.
    Excludes specified book IDs and optionally filters by category and genre.

    Args:
        session: Active database session.
        user_embedding: The user's taste embedding (384 dimensions).
        exclude_book_ids: Book IDs to exclude (already rated).
        category: Filter by "fiction", "nonfiction", or "all".
        limit: Maximum number of results.
        genre_id: Optional genre ID to filter results.

    Returns:
        List of Book objects ordered by cosine similarity.
    """
    stmt = (
        select(Book)
        .options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .where(Book.embedding.isnot(None))
    )

    if exclude_book_ids:
        stmt = stmt.where(Book.id.notin_(exclude_book_ids))

    if category == "fiction":
        stmt = stmt.where(Book.is_fiction == True)  # noqa: E712
    elif category == "nonfiction":
        stmt = stmt.where(Book.is_fiction == False)  # noqa: E712

    if genre_id is not None:
        stmt = stmt.join(BookGenreLink, Book.id == BookGenreLink.book_id).where(
            BookGenreLink.genre_id == genre_id
        )

    stmt = stmt.order_by(
        Book.embedding.cosine_distance(user_embedding)
    ).limit(limit)

    return list(session.exec(stmt).all())
