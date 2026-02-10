"""Embedding assets for the LitMatch recommendation pipeline.

Phase 1: review_embeddings encodes review text into dense vectors
using sentence-transformers. The dimensionality depends on the
configured model.

Phase 2: book_embeddings computes per-book embeddings by averaging
the review embeddings for each book using numpy.

Both assets are incremental -- rows that already have embeddings
are skipped.
"""
import functools
import importlib
from types import ModuleType

import dagster as dg
from sqlmodel import Session, select, update

from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.resources.embedding_model import EmbeddingModelResource


@functools.lru_cache(maxsize=1)
def _models() -> ModuleType:
    """Lazily import and cache the backend.db.models module.

    The backend package lives outside the Dagster src/ layout, so it
    cannot be imported at module-load time during dg dev.
    """
    return importlib.import_module("backend.db.models")


_BATCH_SIZE = 256


def _has_text(text: str | None) -> bool:
    """Return True if text is a non-empty, non-whitespace string."""
    return text is not None and text.strip() != ""


@dg.asset(
    deps=["load_books"],
    description="Generate embeddings for reviews that lack them",
    kinds={"python", "postgres", "ml"},
    retry_policy=dg.RetryPolicy(
        max_retries=1,
        delay=60,
    ),
)
def review_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
    embedding_model: EmbeddingModelResource,
) -> dg.MaterializeResult:
    """Encode review text into dense vectors using sentence-transformers.

    Only processes reviews where embedding IS NULL (incremental).
    Filters out reviews with NULL, empty, or whitespace-only text.
    Encodes in batches of 256 for memory efficiency and commits
    after each batch.

    Returns:
        MaterializeResult with metadata about the encoding operation.
    """
    Review = _models().Review
    engine = database.get_engine()

    try:
        # Query for reviews that need embeddings
        with Session(engine) as session:
            reviews = session.exec(
                select(Review.id, Review.review).where(
                    Review.embedding.is_(None)
                )
            ).all()

        if not reviews:
            context.log.info("All reviews already have embeddings")
            return dg.MaterializeResult(
                metadata={
                    "reviews_encoded": 0,
                    "reviews_skipped": 0,
                    "model_name": embedding_model.model_name,
                    "dimensions": embedding_model.dimensions,
                },
            )

        # Filter out NULL, empty, and whitespace-only review text
        valid_reviews = [(rid, text) for rid, text in reviews if _has_text(text)]
        total_skipped = len(reviews) - len(valid_reviews)

        if total_skipped > 0:
            context.log.warning(
                f"Skipping {total_skipped} reviews with NULL/empty text"
            )

        if not valid_reviews:
            context.log.info(
                "No reviews with valid text to encode after filtering"
            )
            return dg.MaterializeResult(
                metadata={
                    "reviews_encoded": 0,
                    "reviews_skipped": total_skipped,
                    "model_name": embedding_model.model_name,
                    "dimensions": embedding_model.dimensions,
                },
            )

        context.log.info(
            f"Generating embeddings for {len(valid_reviews)} reviews"
        )

        total_encoded = 0

        for i in range(0, len(valid_reviews), _BATCH_SIZE):
            batch = valid_reviews[i : i + _BATCH_SIZE]
            review_ids = [row[0] for row in batch]
            texts = [row[1] for row in batch]

            try:
                embeddings = embedding_model.encode(texts)
            except Exception as exc:
                raise dg.Failure(
                    description=(
                        f"Embedding encode failed on batch starting at "
                        f"offset {i}: {exc}"
                    ),
                ) from exc

            with Session(engine) as session:
                for review_id, emb in zip(review_ids, embeddings):
                    stmt = (
                        update(Review)
                        .where(Review.id == review_id)
                        .values(embedding=emb)
                    )
                    session.execute(stmt)
                session.commit()

            total_encoded += len(batch)
            context.log.info(
                f"Encoded {total_encoded}/{len(valid_reviews)} reviews"
            )

        context.log.info(
            f"Embedding generation complete: {total_encoded} reviews encoded"
        )

        return dg.MaterializeResult(
            metadata={
                "reviews_encoded": total_encoded,
                "reviews_skipped": total_skipped,
                "model_name": embedding_model.model_name,
                "dimensions": embedding_model.dimensions,
            },
        )
    finally:
        engine.dispose()


@dg.asset(
    deps=["review_embeddings"],
    description="Compute book embeddings by averaging review embeddings",
    kinds={"python", "postgres"},
    retry_policy=dg.RetryPolicy(
        max_retries=1,
        delay=60,
    ),
)
def book_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
) -> dg.MaterializeResult:
    """Average review embeddings per book to produce book-level embeddings.

    A book's embedding is the element-wise mean of all its review
    embeddings. Only processes books where:
    - Book.embedding IS NULL (not yet computed)
    - At least one Review with a non-null embedding exists for that book

    Books with zero embedded reviews are skipped.

    Returns:
        MaterializeResult with metadata about the computation.
    """
    from collections import defaultdict

    import numpy as np

    Book = _models().Book
    Review = _models().Review
    engine = database.get_engine()

    try:
        # Find eligible books and fetch all their review embeddings
        # in a single query to avoid N+1 round-trips.
        with Session(engine) as session:
            rows = session.exec(
                select(Review.book_id, Review.embedding)
                .join(Book, Review.book_id == Book.id)
                .where(Book.embedding.is_(None))
                .where(Review.embedding.isnot(None))
            ).all()

        if not rows:
            context.log.info("All books already have embeddings")
            return dg.MaterializeResult(
                metadata={"books_computed": 0},
            )

        # Group review embeddings by book_id
        book_review_map: dict[int, list] = defaultdict(list)
        for book_id, emb in rows:
            book_review_map[book_id].append(emb)

        context.log.info(
            f"Computing embeddings for {len(book_review_map)} books"
        )

        computed = 0

        with Session(engine) as session:
            for book_id, embs in book_review_map.items():
                try:
                    avg_embedding = np.mean(
                        [np.array(emb) for emb in embs],
                        axis=0,
                    ).tolist()
                except Exception as exc:
                    raise dg.Failure(
                        description=(
                            f"Failed to compute mean embedding for "
                            f"book_id={book_id}: {exc}"
                        ),
                    ) from exc

                session.execute(
                    update(Book)
                    .where(Book.id == book_id)
                    .values(embedding=avg_embedding)
                )
                computed += 1

            session.commit()

        context.log.info(
            f"Book embedding computation complete: {computed} books"
        )

        return dg.MaterializeResult(
            metadata={"books_computed": computed},
        )
    finally:
        engine.dispose()
