"""baseline schema

Revision ID: 001
Revises:
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- Independent tables (no foreign keys) ---

    op.create_table(
        "author",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "publisher",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "genre",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "critic",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "publication",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
    )

    # --- Tables with foreign keys ---

    op.create_table(
        "book",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("author.id"), nullable=True),
        sa.Column("publisher_id", sa.Integer(), sa.ForeignKey("publisher.id"), nullable=True),
        sa.Column("publish_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False, unique=True),
        sa.Column("cover", sa.String(), nullable=True),
        sa.Column("is_fiction", sa.Boolean(), nullable=True),
        sa.Column("last_scraped", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
    )

    op.create_table(
        "bookgenrelink",
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("book.id"), primary_key=True),
        sa.Column("genre_id", sa.Integer(), sa.ForeignKey("genre.id"), primary_key=True),
    )

    op.create_table(
        "review",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("book.id"), nullable=False),
        sa.Column("critic_id", sa.Integer(), sa.ForeignKey("critic.id"), nullable=True),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publication.id"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True, unique=True),
        sa.Column("embedding", Vector(384), nullable=True),
    )

    op.create_table(
        "userrating",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("book.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "refreshtoken",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("refreshtoken")
    op.drop_table("userrating")
    op.drop_table("review")
    op.drop_table("bookgenrelink")
    op.drop_table("book")
    op.drop_table("user")
    op.drop_table("publication")
    op.drop_table("critic")
    op.drop_table("genre")
    op.drop_table("publisher")
    op.drop_table("author")
