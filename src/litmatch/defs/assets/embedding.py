"""Embedding assets: generate and store vector embeddings for reviews.

Phase 1 provides review_embeddings, which encodes review text into
dense vectors using sentence-transformers. The dimensionality depends
on the configured model. Reviews that already have embeddings are
skipped (idempotent).
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
