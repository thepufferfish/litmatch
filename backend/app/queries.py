"""Shared query helpers for the backend API."""
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from backend.db.models import Book, BookGenreLink, Review


def build_rating_subquery():
    """Build a subquery that computes avg rating and review count per book."""
    return (
        select(
            Review.book_id,
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .group_by(Review.book_id)
        .subquery()
    )


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcards to prevent pattern injection."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_fts_filter(query_text: str) -> tuple:
    """Build full-text search filter and rank expression.

    Args:
        query_text: User search query text

    Returns:
        Tuple of (filter_clause, rank_expr) for use in WHERE and ORDER BY
    """
    tsquery = func.plainto_tsquery("english", query_text)
    filter_clause = Book.search_vector.op("@@")(tsquery)
    rank_expr = func.ts_rank(Book.search_vector, tsquery)
    return (filter_clause, rank_expr)


def find_similar_books_by_embedding(
    session: Session, book: Book, limit: int = 10
) -> list[Book]:
    """Find similar books using pgvector cosine distance on embeddings.

    Uses the source book's embedding to find nearest neighbors by cosine
    distance. Only considers books that have embeddings and excludes the
    source book itself.

    Args:
        session: Active database session.
        book: The source book whose embedding to compare against.
        limit: Maximum number of similar books to return.

    Returns:
        List of Book objects ordered by cosine similarity (most similar first).
    """
    stmt = (
        select(Book)
        .where(Book.embedding.isnot(None))
        .where(Book.id != book.id)
        .options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .order_by(Book.embedding.cosine_distance(book.embedding))
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def find_similar_books_by_genre(
    session: Session,
    book_id: int,
    genre_ids: list[int],
    limit: int = 10,
) -> list[Book]:
    """Find similar books by genre overlap (fallback when no embedding).

    Joins books to BookGenreLink, filters to books sharing at least one
    genre with the source book, groups by book ID and orders by the number
    of overlapping genres (descending).

    Args:
        session: Active database session.
        book_id: The source book's ID to exclude from results.
        genre_ids: Genre IDs of the source book to match against.
        limit: Maximum number of similar books to return.

    Returns:
        List of Book objects ordered by genre overlap count (most overlap first).
        Returns empty list if genre_ids is empty.
    """
    if not genre_ids:
        return []

    stmt = (
        select(Book)
        .join(BookGenreLink, Book.id == BookGenreLink.book_id)
        .where(BookGenreLink.genre_id.in_(genre_ids))
        .where(Book.id != book_id)
        .group_by(Book.id)
        .order_by(func.count(BookGenreLink.genre_id).desc())
        .options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .limit(limit)
    )
    return list(session.exec(stmt).all())
