import json
import logging
import os
import re
import uuid
from datetime import date, datetime

import psycopg2
from psycopg2.extras import Json
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)

# Commit every N items instead of per-item to reduce fsync overhead.
BATCH_SIZE = 100

# Maximum serialized item size in bytes (1 MB). Rejects oversized items
# to prevent unbounded JSONB storage and OOM when loading into Dagster.
MAX_ITEM_SIZE_BYTES = 1_048_576

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_books_staging (
    id SERIAL PRIMARY KEY,
    crawl_job_id VARCHAR(64) NOT NULL,
    item_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    url TEXT
);
"""

CREATE_INDEXES_SQL = [
    """
    CREATE INDEX IF NOT EXISTS idx_raw_books_staging_crawl_job_id
    ON raw_books_staging (crawl_job_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_raw_books_staging_created_at
    ON raw_books_staging (created_at);
    """,
]

INSERT_ITEM_SQL = """
INSERT INTO raw_books_staging (crawl_job_id, item_data, url)
VALUES (%s, %s, %s);
"""


def _serialize_item(item: dict) -> dict:
    """Convert an item dict to a JSON-serializable dict.

    Converts datetime and date objects to isoformat strings.
    Non-JSON-serializable types are converted to their string representation.
    """
    serialized = {}
    for key, value in item.items():
        if isinstance(value, (datetime, date)):
            serialized[key] = value.isoformat()
        elif isinstance(value, dict):
            serialized[key] = _serialize_item(value)
        elif isinstance(value, list):
            serialized[key] = [
                _serialize_item(v) if isinstance(v, dict)
                else v.isoformat() if isinstance(v, (datetime, date))
                else v if isinstance(v, (str, int, float, bool, type(None)))
                else str(v)
                for v in value
            ]
        elif isinstance(value, (str, int, float, bool, type(None))):
            serialized[key] = value
        else:
            serialized[key] = str(value)
    return serialized


def _sanitize_crawl_job_id(raw_id: str) -> str:
    """Sanitize a crawl job ID to ensure it fits VARCHAR(64) safely.

    Keeps alphanumeric characters, hyphens, and underscores.
    Replaces other characters with underscores and truncates to 64 chars.
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", raw_id)[:64]


class PostgresStagingPipeline:
    """Scrapy pipeline that writes each item to a PostgreSQL staging table.

    Items are batched (committed every BATCH_SIZE items) to reduce
    per-item fsync overhead. A final commit runs in close_spider.
    """

    def __init__(self) -> None:
        self.connection = None
        self.cursor = None
        self.crawl_job_id: str = ""
        self._item_count: int = 0

    def open_spider(self, spider) -> None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is required for "
                "PostgresStagingPipeline"
            )

        self.connection = psycopg2.connect(database_url)
        self.cursor = self.connection.cursor()

        self.cursor.execute(CREATE_TABLE_SQL)
        for index_sql in CREATE_INDEXES_SQL:
            self.cursor.execute(index_sql)
        self.connection.commit()

        raw_job_id = spider.settings.get("_job") or str(uuid.uuid4())
        self.crawl_job_id = _sanitize_crawl_job_id(raw_job_id)
        logger.info(
            "PostgresStagingPipeline opened for crawl job %s",
            self.crawl_job_id,
        )

    def process_item(self, item, spider):
        serialized = _serialize_item(dict(item))

        # Reject oversized items to prevent unbounded storage growth.
        encoded = json.dumps(serialized).encode("utf-8")
        if len(encoded) > MAX_ITEM_SIZE_BYTES:
            url = serialized.get("url", "unknown")
            logger.warning(
                "Item exceeds %d byte limit (%d bytes), dropping: %s",
                MAX_ITEM_SIZE_BYTES,
                len(encoded),
                url,
            )
            raise DropItem(
                f"Item too large ({len(encoded)} bytes): {url}"
            )

        url = serialized.get("url")

        try:
            self.cursor.execute(
                INSERT_ITEM_SQL,
                (self.crawl_job_id, Json(serialized), url),
            )
        except psycopg2.Error:
            self.connection.rollback()
            logger.exception("Failed to insert item: %s", url)
            raise DropItem(f"Database insert failed for {url}")

        self._item_count += 1
        if self._item_count % BATCH_SIZE == 0:
            self.connection.commit()
            logger.debug(
                "Committed batch of %d items (total: %d)",
                BATCH_SIZE,
                self._item_count,
            )

        return item

    def close_spider(self, spider) -> None:
        if self.connection:
            self.connection.commit()
            self.cursor.close()
            self.connection.close()
            logger.info(
                "PostgresStagingPipeline closed for crawl job %s "
                "(%d items written)",
                self.crawl_job_id,
                self._item_count,
            )
