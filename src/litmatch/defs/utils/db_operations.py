"""Database operations for the ETL pipeline.

Handles upserting books, authors, publishers, genres, reviews, critics,
and publications into the database. Expects already-transformed records
(dates as date objects, ratings as ints, critic names cleaned).

Note: backend.db.models imports are deferred because the 'backend' package
lives at the project root, outside the Dagster src/ layout. The dg dev
code server resolves modules from src/ and cannot find 'backend' at
module-load time. Imports happen at function-call time during asset execution,
when the full Python path is available.
"""
from __future__ import annotations

import functools
import importlib
from types import ModuleType
from typing import TYPE_CHECKING

from sqlmodel import Session, select

if TYPE_CHECKING:
    from backend.db.models import (
        Author,
        Book,
        Critic,
        Genre,
        Publication,
        Publisher,
        Review,
    )


@functools.lru_cache(maxsize=1)
def _models() -> ModuleType:
    """Lazily import and cache the backend.db.models module."""
    return importlib.import_module("backend.db.models")


def _get_or_create_author(session: Session, name: str) -> Author:
    """Find an existing author by name, or create a new one."""
    Author = _models().Author
    statement = select(Author).where(Author.name == name)
    author = session.exec(statement).first()
    if not author:
        author = Author(name=name)
        session.add(author)
        session.flush()
    return author


def _get_or_create_publisher(session: Session, name: str) -> Publisher:
    """Find an existing publisher by name, or create a new one."""
    Publisher = _models().Publisher
    statement = select(Publisher).where(Publisher.name == name)
    publisher = session.exec(statement).first()
    if not publisher:
        publisher = Publisher(name=name)
        session.add(publisher)
        session.flush()
    return publisher


def _get_or_create_genre(session: Session, name: str) -> Genre:
    """Find an existing genre by name, or create a new one."""
    Genre = _models().Genre
    statement = select(Genre).where(Genre.name == name)
    genre = session.exec(statement).first()
    if not genre:
        genre = Genre(name=name)
        session.add(genre)
        session.flush()
    return genre


def _get_or_create_critic(session: Session, name: str) -> Critic:
    """Find an existing critic by name, or create a new one."""
    Critic = _models().Critic
    statement = select(Critic).where(Critic.name == name)
    critic = session.exec(statement).first()
    if not critic:
        critic = Critic(name=name)
        session.add(critic)
        session.flush()
    return critic


def _get_or_create_publication(session: Session, name: str) -> Publication:
    """Find an existing publication by name, or create a new one."""
    Publication = _models().Publication
    statement = select(Publication).where(Publication.name == name)
    publication = session.exec(statement).first()
    if not publication:
        publication = Publication(name=name)
        session.add(publication)
        session.flush()
    return publication


def _prepare_reviews(session: Session, reviews: list[dict]) -> list[Review]:
    """Prepare review objects, deduplicating by URL.

    Empty URLs are allowed (68 in real data). Non-empty duplicate URLs
    within the same book are skipped (19 books in real data).

    Args:
        session: Active database session.
        reviews: List of transformed review dicts.

    Returns:
        List of Review model instances.
    """
    Review = _models().Review
    result: list = []
    seen_urls: set[str] = set()

    for review_data in reviews:
        raw_url = review_data.get("url", "")
        # Convert empty strings to None for proper NULL handling in DB.
        # NULL values don't violate unique constraints (NULL != NULL in SQL),
        # allowing multiple reviews without URLs on the same book.
        url: str | None = raw_url if raw_url else None

        # Deduplicate by non-empty URL
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # Check if review already exists in DB (by non-empty URL)
        if url:
            existing = session.exec(
                select(Review).where(Review.url == url)
            ).first()
            if existing:
                result.append(existing)
                continue

        critic = _get_or_create_critic(session, review_data["critic"])
        publication = _get_or_create_publication(session, review_data["publication"])

        review = Review(
            critic=critic,
            publication=publication,
            rating=review_data["rating"],
            review=review_data["review"],
            url=url,
        )
        result.append(review)

    return result


def upsert_book(session: Session, record: dict) -> bool:
    """Insert a new book or update an existing one if the scrape is newer.

    Args:
        session: Active database session. Caller is responsible for committing.
        record: Transformed book record dict (post-transform_book_record).

    Returns:
        True if the book was inserted/updated, False if skipped (older scrape).
    """
    Book = _models().Book

    statement = select(Book).where(Book.url == record["url"])
    existing_book = session.exec(statement).first()

    author = _get_or_create_author(session, record["author"])
    publisher = _get_or_create_publisher(session, record["publisher"])

    if existing_book:
        if existing_book.last_scraped and existing_book.last_scraped >= record["last_scraped"]:
            return False

        existing_book.title = record["title"]
        existing_book.author = author
        existing_book.publisher = publisher
        existing_book.publish_date = record["publish_date"]
        existing_book.description = record["description"]
        existing_book.cover = record["cover"]
        existing_book.is_fiction = record.get("is_fiction")
        existing_book.last_scraped = record["last_scraped"]
        book = existing_book
    else:
        book = Book(
            title=record["title"],
            author=author,
            publisher=publisher,
            publish_date=record["publish_date"],
            description=record["description"],
            url=record["url"],
            cover=record["cover"],
            is_fiction=record.get("is_fiction"),
            last_scraped=record["last_scraped"],
        )
        session.add(book)
        session.flush()

    # Set genres
    genres = [_get_or_create_genre(session, name) for name in record.get("genres", [])]
    book.genres = genres

    # Set reviews
    reviews = _prepare_reviews(session, record.get("reviews", []))
    book.reviews = reviews

    return True
