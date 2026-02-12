import os

from sqlmodel import Session, SQLModel, create_engine, text

from backend.db import models  # noqa: F401 — registers models with SQLModel metadata


def init_db() -> None:
    """Enable the pgvector extension, then create all tables."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable must be set")

    engine = create_engine(database_url, echo=True)
    try:
        # pgvector extension must exist before tables with Vector columns.
        with Session(engine) as session:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
        SQLModel.metadata.create_all(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    init_db()
