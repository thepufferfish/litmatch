import os
import subprocess
import sys

from sqlmodel import Session, create_engine, text


def init_db() -> None:
    """Run Alembic migrations to initialize/upgrade the database schema."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable must be set")

    # Ensure pgvector extension exists before Alembic runs
    engine = create_engine(database_url, echo=False)
    try:
        with Session(engine) as session:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
    finally:
        engine.dispose()

    # Run Alembic upgrade to head
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Alembic migration failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    if result.stdout:
        print(result.stdout)


if __name__ == "__main__":
    init_db()
