"""Shared query helpers for the backend API."""
from sqlmodel import func, select

from backend.db.models import Book, Review


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
