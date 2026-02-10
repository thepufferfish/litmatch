import os

from sqlmodel import Session, SQLModel, create_engine, text

from backend.db import models  # noqa: F401 — registers models with SQLModel metadata


def init_db() -> None:
    """Create all tables and enable the pgvector extension."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable must be set")

    engine = create_engine(database_url, echo=True)
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.exec(text(
                "ALTER TABLE review "
                "ADD COLUMN IF NOT EXISTS embedding vector(384)"
            ))
            session.exec(text(
                "ALTER TABLE book "
                "ADD COLUMN IF NOT EXISTS embedding vector(384)"
            ))
            session.commit()
    finally:
        engine.dispose()


if __name__ == "__main__":
    init_db()
