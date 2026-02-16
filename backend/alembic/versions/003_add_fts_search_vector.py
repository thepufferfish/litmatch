"""add full-text search support

Revision ID: 003
Revises: 002
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add search_vector column to book table
    op.add_column(
        "book",
        sa.Column("search_vector", TSVECTOR, nullable=True)
    )

    # Create trigger function to update search_vector on book changes
    op.execute("""
        CREATE OR REPLACE FUNCTION book_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(
                    (SELECT name FROM author WHERE id = NEW.author_id), ''
                )), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on book table for INSERT or UPDATE
    op.execute("""
        CREATE TRIGGER book_search_vector_trigger
        BEFORE INSERT OR UPDATE OF title, author_id, description
        ON book
        FOR EACH ROW
        EXECUTE FUNCTION book_search_vector_update();
    """)

    # Create trigger function to update book search vectors when author name changes
    op.execute("""
        CREATE OR REPLACE FUNCTION author_name_change_update_books()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.name IS DISTINCT FROM NEW.name THEN
                UPDATE book
                SET search_vector =
                    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'B') ||
                    setweight(to_tsvector('english', COALESCE(description, '')), 'C')
                WHERE author_id = NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger on author table for UPDATE
    op.execute("""
        CREATE TRIGGER author_name_change_trigger
        AFTER UPDATE OF name
        ON author
        FOR EACH ROW
        EXECUTE FUNCTION author_name_change_update_books();
    """)

    # Backfill existing rows with search vectors
    op.execute("""
        UPDATE book
        SET search_vector =
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(
                (SELECT name FROM author WHERE id = book.author_id), ''
            )), 'B') ||
            setweight(to_tsvector('english', COALESCE(description, '')), 'C');
    """)

    # Create GIN index on search_vector for fast full-text search
    op.create_index(
        "idx_book_search_vector",
        "book",
        ["search_vector"],
        postgresql_using="gin"
    )


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index("idx_book_search_vector", table_name="book")
    op.execute("DROP TRIGGER IF EXISTS author_name_change_trigger ON author")
    op.execute("DROP FUNCTION IF EXISTS author_name_change_update_books()")
    op.execute("DROP TRIGGER IF EXISTS book_search_vector_trigger ON book")
    op.execute("DROP FUNCTION IF EXISTS book_search_vector_update()")
    op.drop_column("book", "search_vector")
