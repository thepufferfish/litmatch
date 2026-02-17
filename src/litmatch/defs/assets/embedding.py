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

_EXPECTED_DIM = 384


def _has_text(text: str | None) -> bool:
    """Return True if text is a non-empty, non-whitespace string."""
    return text is not None and text.strip() != ""


def _validate_embedding_dims(embeddings: list[list[float]], context: str) -> None:
    """Validate that all embeddings have the expected dimensionality.

    Args:
        embeddings: List of embedding vectors to validate.
        context: Description of where the embeddings came from (for error messages).

    Raises:
        dg.Failure: If any embedding has wrong dimensions.
    """
    for i, emb in enumerate(embeddings):
        if len(emb) != _EXPECTED_DIM:
            raise dg.Failure(
                description=(
                    f"Embedding dimension mismatch in {context} at index {i}: "
                    f"expected {_EXPECTED_DIM}, got {len(emb)}"
                ),
            )


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

            _validate_embedding_dims(embeddings, f"review batch at offset {i}")

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
    deps=["load_books"],
    description="Generate embeddings for genres that lack them",
    kinds={"python", "postgres", "ml"},
    retry_policy=dg.RetryPolicy(
        max_retries=1,
        delay=60,
    ),
)
def genre_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
    embedding_model: EmbeddingModelResource,
) -> dg.MaterializeResult:
    """Encode genre names into dense vectors using sentence-transformers.

    Only processes genres where embedding IS NULL (incremental).
    Genre names are short strings (e.g. "Literary Fiction"), so all
    genres are encoded in a single batch call.

    Returns:
        MaterializeResult with metadata about the encoding operation.
    """
    Genre = _models().Genre
    engine = database.get_engine()

    try:
        with Session(engine) as session:
            genres = session.exec(
                select(Genre.id, Genre.name).where(Genre.embedding.is_(None))
            ).all()

        if not genres:
            context.log.info("All genres already have embeddings")
            return dg.MaterializeResult(
                metadata={
                    "genres_embedded": 0,
                    "model_name": embedding_model.model_name,
                    "dimensions": embedding_model.dimensions,
                },
            )

        genre_ids = [row[0] for row in genres]
        genre_names = [row[1] for row in genres]

        context.log.info(f"Generating embeddings for {len(genre_ids)} genres")

        try:
            embeddings = embedding_model.encode(genre_names)
        except Exception as exc:
            raise dg.Failure(
                description=f"Embedding encode failed for genres: {exc}",
            ) from exc

        _validate_embedding_dims(embeddings, "genre batch")

        with Session(engine) as session:
            for genre_id, emb in zip(genre_ids, embeddings):
                session.execute(
                    update(Genre)
                    .where(Genre.id == genre_id)
                    .values(embedding=emb)
                )
            session.commit()

        context.log.info(
            f"Genre embedding generation complete: {len(genre_ids)} genres embedded"
        )

        return dg.MaterializeResult(
            metadata={
                "genres_embedded": len(genre_ids),
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
    - BookEmbedding.review_embedding IS NULL (not yet computed)
    - At least one Review with a non-null embedding exists for that book

    Books with zero embedded reviews are skipped.

    Returns:
        MaterializeResult with metadata about the computation.
    """
    from collections import defaultdict
    from datetime import datetime, timezone

    import numpy as np

    Book = _models().Book
    BookEmbedding = _models().BookEmbedding
    Review = _models().Review
    engine = database.get_engine()

    try:
        # Find eligible books: those without BookEmbedding rows or with NULL review_embedding
        with Session(engine) as session:
            # Get all book_ids that have reviews with embeddings
            books_with_reviews = session.execute(
                select(Review.book_id)
                .where(Review.embedding.isnot(None))
                .distinct()
            ).all()

            if not books_with_reviews:
                context.log.info("No books with embedded reviews found")
                return dg.MaterializeResult(
                    metadata={"books_computed": 0},
                )

            # Get existing book_embeddings that already have review_embedding
            existing_embeddings = session.execute(
                select(BookEmbedding.book_id)
                .where(BookEmbedding.review_embedding.isnot(None))
            ).all()

            existing_set = set(row[0] for row in existing_embeddings)
            eligible_book_ids = [
                row[0] for row in books_with_reviews if row[0] not in existing_set
            ]

            if not eligible_book_ids:
                context.log.info("All books already have review embeddings")
                return dg.MaterializeResult(
                    metadata={"books_computed": 0},
                )

            # Fetch review embeddings for eligible books
            rows = session.execute(
                select(Review.book_id, Review.embedding)
                .where(Review.book_id.in_(eligible_book_ids))
                .where(Review.embedding.isnot(None))
            ).all()

        # Group review embeddings by book_id
        book_review_map: dict[int, list] = defaultdict(list)
        for book_id, emb in rows:
            book_review_map[book_id].append(emb)

        context.log.info(
            f"Computing review embeddings for {len(book_review_map)} books"
        )

        computed = 0

        with Session(engine) as session:
            # Pre-fetch all existing book_ids in one query to avoid N+1 SELECTs
            existing_ids = {
                row[0]
                for row in session.execute(
                    select(BookEmbedding.book_id).where(
                        BookEmbedding.book_id.in_(list(book_review_map.keys()))
                    )
                ).all()
            }

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

                if book_id in existing_ids:
                    # Update existing row
                    session.execute(
                        update(BookEmbedding)
                        .where(BookEmbedding.book_id == book_id)
                        .values(
                            review_embedding=avg_embedding,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                else:
                    # Insert new row
                    new_embedding = BookEmbedding(
                        book_id=book_id,
                        review_embedding=avg_embedding,
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(new_embedding)

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


@dg.asset(
    deps=["load_books"],
    description="Generate embeddings for book descriptions that lack them",
    kinds={"python", "postgres", "ml"},
    retry_policy=dg.RetryPolicy(
        max_retries=1,
        delay=60,
    ),
)
def book_description_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
    embedding_model: EmbeddingModelResource,
) -> dg.MaterializeResult:
    """Encode book description text into dense vectors using sentence-transformers.

    Only processes books where description is non-NULL/non-empty AND the
    corresponding BookEmbedding row has description_embedding IS NULL
    (incremental). Uses LEFT JOIN logic to find books needing embeddings,
    including those with no BookEmbedding row yet.

    For each book:
    - If a BookEmbedding row exists: UPDATE description_embedding
    - If no BookEmbedding row exists: INSERT a new one

    Processes in batches of 256, committing after each batch.

    Returns:
        MaterializeResult with metadata about the encoding operation.
    """
    from datetime import datetime, timezone

    Book = _models().Book
    BookEmbedding = _models().BookEmbedding
    engine = database.get_engine()

    try:
        # Query books needing description embeddings via LEFT JOIN
        with Session(engine) as session:
            rows = session.execute(
                select(Book.id, Book.description)
                .outerjoin(BookEmbedding, BookEmbedding.book_id == Book.id)
                .where(Book.description.isnot(None))
                .where(BookEmbedding.description_embedding.is_(None))
            ).all()

        if not rows:
            context.log.info("All books already have description embeddings")
            return dg.MaterializeResult(
                metadata={
                    "books_embedded": 0,
                    "books_skipped": 0,
                    "model_name": embedding_model.model_name,
                    "dimensions": embedding_model.dimensions,
                },
            )

        # Filter out NULL, empty, and whitespace-only descriptions
        valid_books = [(book_id, desc) for book_id, desc in rows if _has_text(desc)]
        total_skipped = len(rows) - len(valid_books)

        if total_skipped > 0:
            context.log.warning(
                f"Skipping {total_skipped} books with NULL/empty descriptions"
            )

        if not valid_books:
            context.log.info(
                "No books with valid description text to encode after filtering"
            )
            return dg.MaterializeResult(
                metadata={
                    "books_embedded": 0,
                    "books_skipped": total_skipped,
                    "model_name": embedding_model.model_name,
                    "dimensions": embedding_model.dimensions,
                },
            )

        context.log.info(
            f"Generating description embeddings for {len(valid_books)} books"
        )

        total_embedded = 0

        for i in range(0, len(valid_books), _BATCH_SIZE):
            batch = valid_books[i : i + _BATCH_SIZE]
            book_ids = [row[0] for row in batch]
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

            _validate_embedding_dims(embeddings, f"description batch at offset {i}")

            with Session(engine) as session:
                # Pre-fetch all existing book_ids in one query to avoid N+1 SELECTs
                existing_ids = {
                    row[0]
                    for row in session.execute(
                        select(BookEmbedding.book_id).where(
                            BookEmbedding.book_id.in_(book_ids)
                        )
                    ).all()
                }

                for book_id, emb in zip(book_ids, embeddings):
                    if book_id in existing_ids:
                        session.execute(
                            update(BookEmbedding)
                            .where(BookEmbedding.book_id == book_id)
                            .values(
                                description_embedding=emb,
                                updated_at=datetime.now(timezone.utc),
                            )
                        )
                    else:
                        new_embedding = BookEmbedding(
                            book_id=book_id,
                            description_embedding=emb,
                            updated_at=datetime.now(timezone.utc),
                        )
                        session.add(new_embedding)

                session.commit()

            total_embedded += len(batch)
            context.log.info(
                f"Embedded {total_embedded}/{len(valid_books)} book descriptions"
            )

        context.log.info(
            f"Description embedding complete: {total_embedded} books embedded"
        )

        return dg.MaterializeResult(
            metadata={
                "books_embedded": total_embedded,
                "books_skipped": total_skipped,
                "model_name": embedding_model.model_name,
                "dimensions": embedding_model.dimensions,
            },
        )
    finally:
        engine.dispose()


@dg.asset(
    deps=["genre_embeddings"],
    description="Compute book genre embeddings by averaging genre embeddings per book",
    kinds={"python", "postgres"},
    retry_policy=dg.RetryPolicy(
        max_retries=1,
        delay=60,
    ),
)
def book_genre_embeddings(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
) -> dg.MaterializeResult:
    """Average genre embeddings per book to produce book-level genre embeddings.

    A book's genre embedding is the element-wise mean of all its associated
    genre embeddings. Only processes books where:
    - At least one linked Genre has a non-null embedding
    - The corresponding BookEmbedding row has genre_embedding IS NULL (not yet computed)

    Books with no genres that have embeddings are skipped. All genre embeddings
    for eligible books are batch-fetched in a single query to avoid N+1 queries.

    Returns:
        MaterializeResult with metadata about the computation.
    """
    from collections import defaultdict
    from datetime import datetime, timezone

    import numpy as np

    BookEmbedding = _models().BookEmbedding
    BookGenreLink = _models().BookGenreLink
    Genre = _models().Genre
    engine = database.get_engine()

    try:
        with Session(engine) as session:
            # Find book_ids that have at least one genre with a non-null embedding,
            # but whose BookEmbedding row has genre_embedding IS NULL.
            # Uses LEFT JOIN so books with no BookEmbedding row are also included.
            eligible_rows = session.execute(
                select(BookGenreLink.book_id)
                .join(Genre, Genre.id == BookGenreLink.genre_id)
                .outerjoin(
                    BookEmbedding, BookEmbedding.book_id == BookGenreLink.book_id
                )
                .where(Genre.embedding.isnot(None))
                .where(BookEmbedding.genre_embedding.is_(None))
                .distinct()
            ).all()

            if not eligible_rows:
                context.log.info(
                    "All books already have genre embeddings or no eligible books found"
                )
                return dg.MaterializeResult(
                    metadata={"books_computed": 0},
                )

            eligible_book_ids = [row[0] for row in eligible_rows]

            context.log.info(
                f"Found {len(eligible_book_ids)} books needing genre embeddings"
            )

            # Batch-fetch all genre embeddings for eligible books in one query
            genre_rows = session.execute(
                select(BookGenreLink.book_id, Genre.embedding)
                .join(Genre, Genre.id == BookGenreLink.genre_id)
                .where(BookGenreLink.book_id.in_(eligible_book_ids))
                .where(Genre.embedding.isnot(None))
            ).all()

        # Group genre embeddings by book_id in Python
        book_genre_map: dict[int, list] = defaultdict(list)
        for book_id, emb in genre_rows:
            book_genre_map[book_id].append(emb)

        context.log.info(
            f"Computing genre embeddings for {len(book_genre_map)} books"
        )

        computed = 0

        with Session(engine) as session:
            # Pre-fetch all existing book_ids in one query to avoid N+1 SELECTs
            existing_ids = {
                row[0]
                for row in session.execute(
                    select(BookEmbedding.book_id).where(
                        BookEmbedding.book_id.in_(list(book_genre_map.keys()))
                    )
                ).all()
            }

            for book_id, embs in book_genre_map.items():
                try:
                    avg_embedding = np.mean(
                        [np.array(emb) for emb in embs],
                        axis=0,
                    ).tolist()
                except Exception as exc:
                    raise dg.Failure(
                        description=(
                            f"Failed to compute mean genre embedding for "
                            f"book_id={book_id}: {exc}"
                        ),
                    ) from exc

                if book_id in existing_ids:
                    session.execute(
                        update(BookEmbedding)
                        .where(BookEmbedding.book_id == book_id)
                        .values(
                            genre_embedding=avg_embedding,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                else:
                    new_embedding = BookEmbedding(
                        book_id=book_id,
                        genre_embedding=avg_embedding,
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(new_embedding)

                computed += 1

            session.commit()

        context.log.info(
            f"Book genre embedding computation complete: {computed} books"
        )

        return dg.MaterializeResult(
            metadata={"books_computed": computed},
        )
    finally:
        engine.dispose()


def _l2_normalize(vec: "np.ndarray") -> "np.ndarray":
    """Return the L2-normalized form of vec.

    If the vector has zero norm (all zeros), return it unchanged to avoid
    division by zero.
    """
    import numpy as np

    norm = np.linalg.norm(vec)
    if norm == 0.0:
        return vec
    return vec / norm


class _CompositeConfig(dg.Config):
    force_recompute: bool = False


@dg.asset(
    deps=["book_embeddings", "book_description_embeddings", "book_genre_embeddings"],
    description=(
        "Concatenate per-book sub-embeddings into a single 1152-dim composite vector"
    ),
    kinds={"python", "postgres"},
    retry_policy=dg.RetryPolicy(
        max_retries=1,
        delay=60,
    ),
)
def composite_book_embeddings(
    context: dg.AssetExecutionContext,
    config: _CompositeConfig,
    database: DatabaseResource,
) -> dg.MaterializeResult:
    """Build a 1152-dim composite embedding for every BookEmbedding row.

    Concatenation contract (order is a fixed API surface):
        dims   0 –  383 : review_embedding   (L2-normalised, or zeros if NULL)
        dims 384 –  767 : description_embedding (L2-normalised, or zeros if NULL)
        dims 768 – 1151 : genre_embedding    (L2-normalised, or zeros if NULL)

    Each 384-dim sub-vector is L2-normalised independently before concatenation
    so that every signal contributes equally regardless of its raw magnitude.
    Missing signals are zero-padded (cold-start behaviour). The final 1152-dim
    vector is stored raw (NOT L2-normalised) so that its norm encodes signal
    completeness:

        all 3 signals → norm ≈ sqrt(3) ≈ 1.73
        2 signals     → norm ≈ sqrt(2) ≈ 1.41
        1 signal      → norm ≈ 1.0

    Args:
        config: ``force_recompute=True`` reprocesses every row that has at
            least one sub-embedding, even if ``embedding`` is already set.
            Default (False) skips rows where ``embedding IS NOT NULL``.

    Returns:
        MaterializeResult with metadata: total_computed, three_signal,
        two_signal, one_signal, skipped_no_signal.
    """
    from datetime import datetime, timezone

    import numpy as np

    BookEmbedding = _models().BookEmbedding
    engine = database.get_engine()

    _ZERO = np.zeros(_EXPECTED_DIM, dtype=np.float32)

    try:
        total_computed = 0
        three_signal = 0
        two_signal = 0
        one_signal = 0
        skipped_no_signal = 0
        batch_num = 0
        found_any = False

        while True:
            with Session(engine) as session:
                stmt = select(
                    BookEmbedding.book_id,
                    BookEmbedding.review_embedding,
                    BookEmbedding.description_embedding,
                    BookEmbedding.genre_embedding,
                )

                if not config.force_recompute:
                    # Without force_recompute, rows are committed with embedding set,
                    # so always query from offset 0 (eligible rows shrink each batch)
                    stmt = stmt.where(BookEmbedding.embedding.is_(None))
                    rows = session.execute(stmt.limit(_BATCH_SIZE)).all()
                else:
                    # With force_recompute, rows already have embeddings so we must
                    # use offset-based pagination to avoid re-reading the same rows
                    rows = session.execute(
                        stmt.limit(_BATCH_SIZE).offset(batch_num * _BATCH_SIZE)
                    ).all()

                if not rows:
                    break

                found_any = True
                context.log.info(
                    f"Computing composite embeddings for batch {batch_num} "
                    f"({len(rows)} rows, force_recompute={config.force_recompute})"
                )

                for book_id, review_emb, desc_emb, genre_emb in rows:
                    sub_embeddings = [review_emb, desc_emb, genre_emb]
                    signal_count = sum(1 for e in sub_embeddings if e is not None)

                    if signal_count == 0:
                        skipped_no_signal += 1
                        continue

                    # Validate dimensions of non-null sub-embeddings
                    for vec, name in [
                        (review_emb, "review"),
                        (desc_emb, "description"),
                        (genre_emb, "genre"),
                    ]:
                        if vec is not None and len(vec) != _EXPECTED_DIM:
                            raise dg.Failure(
                                description=(
                                    f"book_id={book_id}: {name}_embedding has wrong dim "
                                    f"{len(vec)}, expected {_EXPECTED_DIM}"
                                )
                            )

                    # L2-normalise each available sub-embedding; zero-pad if missing.
                    # Fixed order: review | description | genre
                    review_vec = (
                        _l2_normalize(np.array(review_emb, dtype=np.float32))
                        if review_emb is not None
                        else _ZERO.copy()
                    )
                    desc_vec = (
                        _l2_normalize(np.array(desc_emb, dtype=np.float32))
                        if desc_emb is not None
                        else _ZERO.copy()
                    )
                    genre_vec = (
                        _l2_normalize(np.array(genre_emb, dtype=np.float32))
                        if genre_emb is not None
                        else _ZERO.copy()
                    )

                    # Concatenate in fixed order → 1152-dim; do NOT normalise the result.
                    composite = np.concatenate([review_vec, desc_vec, genre_vec]).tolist()

                    session.execute(
                        update(BookEmbedding)
                        .where(BookEmbedding.book_id == book_id)
                        .values(
                            embedding=composite,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )

                    total_computed += 1
                    if signal_count == 3:
                        three_signal += 1
                    elif signal_count == 2:
                        two_signal += 1
                    else:
                        one_signal += 1

                session.commit()

            batch_num += 1
            context.log.info(
                f"Processed composite batch, total computed so far: {total_computed}"
            )

        if not found_any:
            context.log.info(
                "No BookEmbedding rows require composite embedding computation"
            )

        context.log.info(
            f"Composite embedding complete: {total_computed} computed, "
            f"{skipped_no_signal} skipped (no signal)"
        )

        return dg.MaterializeResult(
            metadata={
                "total_computed": total_computed,
                "three_signal": three_signal,
                "two_signal": two_signal,
                "one_signal": one_signal,
                "skipped_no_signal": skipped_no_signal,
            },
        )
    finally:
        engine.dispose()
