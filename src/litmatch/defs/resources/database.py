"""Database resource for the Dagster ETL pipeline.

Provides a configured SQLAlchemy engine as a Dagster resource.
"""
import dagster as dg
from sqlalchemy import Engine, create_engine


class DatabaseResource(dg.ConfigurableResource):
    """Dagster resource wrapping a SQLAlchemy database engine.

    Reads connection string from the DAGSTER_DATABASE_URL environment variable
    by default, with an override via the connection_string config.
    """

    connection_string: str

    def get_engine(self) -> Engine:
        """Create and return a SQLAlchemy engine."""
        return create_engine(self.connection_string, echo=False)
