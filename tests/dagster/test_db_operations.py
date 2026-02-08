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
    is_fiction: bool | None = True,
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
        "is_fiction": is_fiction,
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

    def test_is_fiction_persists_on_insert(self) -> None:
        """HIGH-3: is_fiction field should be stored in the database."""
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Book

        engine = _create_engine_and_tables()
        record = _make_transformed_record(is_fiction=True)

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            book = session.exec(select(Book)).first()
            assert book is not None
            assert book.is_fiction is True

    def test_is_fiction_persists_on_update(self) -> None:
        """HIGH-3: is_fiction should be updated when book is re-scraped."""
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Book

        engine = _create_engine_and_tables()
        record_old = _make_transformed_record(
            is_fiction=True,
            last_scraped=datetime(2025, 1, 1),
        )
        record_new = _make_transformed_record(
            is_fiction=False,
            last_scraped=datetime(2025, 10, 13),
        )

        with Session(engine) as session:
            upsert_book(session, record_old)
            session.commit()

        with Session(engine) as session:
            upsert_book(session, record_new)
            session.commit()

        with Session(engine) as session:
            book = session.exec(select(Book)).first()
            assert book is not None
            assert book.is_fiction is False

    def test_is_fiction_none_for_unclassified(self) -> None:
        """HIGH-3: Books with no fiction classification should have is_fiction=None."""
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Book

        engine = _create_engine_and_tables()
        record = _make_transformed_record(is_fiction=None)

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            book = session.exec(select(Book)).first()
            assert book is not None
            assert book.is_fiction is None

    def test_multiple_empty_urls_same_book(self) -> None:
        """HIGH-5: Multiple reviews with empty URLs on the same book must all be stored.

        Empty URLs should be converted to None so they don't violate
        the unique constraint (NULL != NULL in SQL).
        """
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Review

        engine = _create_engine_and_tables()
        record = _make_transformed_record(reviews=[
            {
                "critic": "Critic A",
                "publication": "Pub A",
                "rating": 4,
                "review": "First review with no URL.",
                "url": "",
            },
            {
                "critic": "Critic B",
                "publication": "Pub B",
                "rating": 3,
                "review": "Second review with no URL.",
                "url": "",
            },
        ])

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            reviews = session.exec(select(Review)).all()
            assert len(reviews) == 2
            # Both should have None URL, not empty string
            assert reviews[0].url is None
            assert reviews[1].url is None

    def test_empty_url_converted_to_none(self) -> None:
        """HIGH-5: Empty string URLs should become None in the database."""
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session, select
        from backend.db.models import Review

        engine = _create_engine_and_tables()
        record = _make_transformed_record(reviews=[
            {
                "critic": "Test Critic",
                "publication": "Test Pub",
                "rating": 4,
                "review": "A review.",
                "url": "",
            },
        ])

        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()

        with Session(engine) as session:
            review = session.exec(select(Review)).first()
            assert review is not None
            assert review.url is None


class TestModelsLazyImport:
    """HIGH-2: _models() should use functools.lru_cache, not global mutable state."""

    def test_models_uses_lru_cache(self) -> None:
        """Verify _models does not use global mutable state."""
        from litmatch.defs.utils import db_operations

        # The _models function should be a cached function (lru_cache)
        assert hasattr(db_operations._models, "cache_info"), (
            "_models should use functools.lru_cache, not global mutable state"
        )

    def test_no_global_models_module_variable(self) -> None:
        """Verify the global _models_module variable was removed."""
        from litmatch.defs.utils import db_operations

        assert not hasattr(db_operations, "_models_module"), (
            "Global _models_module variable should be removed in favor of lru_cache"
        )
