"""Tests for database operations (upsert logic).

Uses an in-memory SQLite database for isolation.
All transforms should already be applied before these functions are called.
"""
import pytest
from datetime import date, datetime


def _create_engine_and_tables():
    """Create a fresh in-memory SQLite engine with all tables."""
    from sqlalchemy import create_engine
    from sqlmodel import SQLModel

    # Import models to register them with SQLModel.metadata
    import backend.db.models  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _make_transformed_record(
    title: str = "Test Book",
    author: str = "Test Author",
    publisher: str = "Test Publisher",
    publish_date: date | None = None,
    description: str = "A test book.",
    genres: list[str] | None = None,
    url: str = "https://bookmarks.reviews/reviews/test-book/",
    cover: str | None = None,
    last_scraped: datetime | None = None,
    reviews: list[dict] | None = None,
) -> dict:
    """Helper to create a transformed (post-transform) record."""
    return {
        "title": title,
        "author": author,
        "publisher": publisher,
        "publish_date": publish_date or date(2025, 1, 1),
        "description": description,
        "genres": genres or ["Fiction"],
        "url": url,
        "cover": cover,
        "last_scraped": last_scraped or datetime(2025, 10, 13, 11, 0, 0),
        "is_fiction": True,
        "reviews": reviews or [
            {
                "critic": "John Self",
                "publication": "Financial Times",
                "rating": 4,
                "review": "A brilliant work.",
                "url": "https://ft.com/review/test-book",
            }
        ],
    }


class TestUpsertBook:
    """Tests for upsert_book: inserts or updates a book in the database."""

    def test_insert_new_book(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Book

        engine = _create_engine_and_tables()
        record = _make_transformed_record()

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            book = session.exec(select(Book)).first()
            assert book is not None
            assert book.title == "Test Book"
            assert book.url == record["url"]

    def test_insert_creates_author(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Author

        engine = _create_engine_and_tables()
        record = _make_transformed_record()

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            author = session.exec(select(Author)).first()
            assert author is not None
            assert author.name == "Test Author"

    def test_insert_creates_publisher(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Publisher

        engine = _create_engine_and_tables()
        record = _make_transformed_record()

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            publisher = session.exec(select(Publisher)).first()
            assert publisher is not None
            assert publisher.name == "Test Publisher"

    def test_insert_creates_genres(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Genre

        engine = _create_engine_and_tables()
        record = _make_transformed_record(genres=["Fiction", "Literary"])

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            genres = session.exec(select(Genre)).all()
            assert len(genres) == 2
            genre_names = {g.name for g in genres}
            assert genre_names == {"Fiction", "Literary"}

    def test_insert_creates_reviews(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Review

        engine = _create_engine_and_tables()
        record = _make_transformed_record()

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            reviews = session.exec(select(Review)).all()
            assert len(reviews) == 1
            assert reviews[0].rating == 4

    def test_update_existing_book_newer_scrape(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Book

        engine = _create_engine_and_tables()
        record_old = _make_transformed_record(
            title="Old Title",
            last_scraped=datetime(2025, 1, 1),
        )
        record_new = _make_transformed_record(
            title="New Title",
            last_scraped=datetime(2025, 10, 13),
        )

        with Session(engine) as session:
            upsert_book(session, record_old)
            session.commit()

        with Session(engine) as session:
            upsert_book(session, record_new)
            session.commit()

        with Session(engine) as session:
            books = session.exec(select(Book)).all()
            assert len(books) == 1
            assert books[0].title == "New Title"

    def test_skip_existing_book_older_scrape(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Book

        engine = _create_engine_and_tables()
        record_new = _make_transformed_record(
            title="New Title",
            last_scraped=datetime(2025, 10, 13),
        )
        record_old = _make_transformed_record(
            title="Old Title",
            last_scraped=datetime(2025, 1, 1),
        )

        with Session(engine) as session:
            upsert_book(session, record_new)
            session.commit()

        with Session(engine) as session:
            result = upsert_book(session, record_old)
            session.commit()

        assert result is False  # Should indicate skip

        with Session(engine) as session:
            books = session.exec(select(Book)).all()
            assert len(books) == 1
            assert books[0].title == "New Title"

    def test_reuses_existing_author(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Author

        engine = _create_engine_and_tables()
        record1 = _make_transformed_record(
            url="https://bookmarks.reviews/reviews/book-1/"
        )
        record2 = _make_transformed_record(
            title="Another Book",
            url="https://bookmarks.reviews/reviews/book-2/",
        )

        with Session(engine) as session:
            upsert_book(session, record1)
            session.commit()
        with Session(engine) as session:
            upsert_book(session, record2)
            session.commit()

        with Session(engine) as session:
            authors = session.exec(select(Author)).all()
            assert len(authors) == 1  # Same author reused

    def test_deduplicates_review_urls(self) -> None:
        """Duplicate review URLs within a book should be skipped (19 books in real data)."""
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Review

        engine = _create_engine_and_tables()
        dup_url = "https://ft.com/review/test-book"
        record = _make_transformed_record(reviews=[
            {
                "critic": "John Self",
                "publication": "Financial Times",
                "rating": 4,
                "review": "First review.",
                "url": dup_url,
            },
            {
                "critic": "John Self",
                "publication": "Financial Times",
                "rating": 3,
                "review": "Duplicate URL review.",
                "url": dup_url,
            },
        ])

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            reviews = session.exec(select(Review)).all()
            assert len(reviews) == 1
            assert reviews[0].review == "First review."

    def test_handles_empty_review_url(self) -> None:
        """68 reviews in real data have empty URLs -- they should still be inserted."""
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Review

        engine = _create_engine_and_tables()
        record = _make_transformed_record(reviews=[
            {
                "critic": "Anonymous",
                "publication": "Unknown",
                "rating": 4,
                "review": "Great book with no URL.",
                "url": "",
            },
        ])

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            reviews = session.exec(select(Review)).all()
            assert len(reviews) == 1

    def test_creates_critic_and_publication(self) -> None:
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Critic, Publication

        engine = _create_engine_and_tables()
        record = _make_transformed_record()

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            critics = session.exec(select(Critic)).all()
            assert len(critics) == 1
            assert critics[0].name == "John Self"

            publications = session.exec(select(Publication)).all()
            assert len(publications) == 1
            assert publications[0].name == "Financial Times"
