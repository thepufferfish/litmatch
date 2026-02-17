"""create book_embeddings table and migrate data

Revision ID: 004
Revises: 003
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create book_embeddings table
    op.create_table(
        "book_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("review_embedding", Vector(384), nullable=True),
        sa.Column("description_embedding", Vector(384), nullable=True),
        sa.Column("genre_embedding", Vector(384), nullable=True),
        sa.Column("embedding", Vector(1152), nullable=True),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["book.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id"),
    )

    # Create index on book_id for fast lookups
    op.create_index(
        "ix_book_embeddings_book_id",
        "book_embeddings",
        ["book_id"],
    )

    # Create HNSW indexes for approximate nearest-neighbor search
    op.execute("""
        CREATE INDEX ix_book_embeddings_embedding_hnsw
        ON book_embeddings USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    op.execute("""
        CREATE INDEX ix_book_embeddings_review_embedding_hnsw
        ON book_embeddings USING hnsw (review_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Migrate existing Book.embedding data to BookEmbedding.review_embedding
    op.execute("""
        INSERT INTO book_embeddings (book_id, review_embedding, updated_at)
        SELECT id, embedding, NOW()
        FROM book
        WHERE embedding IS NOT NULL
    """)

    # Drop the embedding column from book table
    op.drop_column("book", "embedding")

    # Add embedding column to genre table
    op.add_column(
        "genre",
        sa.Column("embedding", Vector(384), nullable=True),
    )


def downgrade() -> None:
    # Remove embedding column from genre table
    op.drop_column("genre", "embedding")

    # Re-add embedding column to book table
    op.add_column(
        "book",
        sa.Column("embedding", Vector(384), nullable=True),
    )

    # Migrate data back from book_embeddings.review_embedding to book.embedding
    op.execute("""
        UPDATE book
        SET embedding = book_embeddings.review_embedding
        FROM book_embeddings
        WHERE book.id = book_embeddings.book_id
    """)

    # Drop HNSW indexes
    op.execute("DROP INDEX IF EXISTS ix_book_embeddings_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_book_embeddings_review_embedding_hnsw")

    # Drop index
    op.drop_index("ix_book_embeddings_book_id", table_name="book_embeddings")

    # Drop book_embeddings table
    op.drop_table("book_embeddings")
