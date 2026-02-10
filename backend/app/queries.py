"""Shared query helpers for the backend API."""
from sqlmodel import func, select

from backend.db.models import Review


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
