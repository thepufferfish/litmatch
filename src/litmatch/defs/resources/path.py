"""Path configuration resource for the Dagster ETL pipeline.

Provides configurable file paths for input data sources.
"""
import dagster as dg


class PathResource(dg.ConfigurableResource):
    """Dagster resource for file path configuration.

    Provides the path to the raw JSONL data directory.
    Defaults to the local scraper output path.
    """

    raw_data_dir: str = "scraper/output/raw"

    @property
    def books_jsonl_path(self) -> str:
        """Full path to the books.jsonl file."""
        return f"{self.raw_data_dir}/books.jsonl"

    @property
    def quarantine_dir(self) -> str:
        """Full path to the quarantine directory for validation errors."""
        return f"{self.raw_data_dir}/quarantine"
