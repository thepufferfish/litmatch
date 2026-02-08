import os

import dagster as dg

from litmatch.defs.assets.extract import raw_books
from litmatch.defs.assets.load import load_books
from litmatch.defs.assets.transform import cleaned_books
from litmatch.defs.assets.validate import validate_raw_books
from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.resources.path import PathResource

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://bookuser:bookpassword@localhost:5432/bookdb",
)
_RAW_DATA_DIR = os.environ.get(
    "RAW_DATA_DIR",
    "scraper/output/raw",
)


@dg.definitions
def defs():
    return dg.Definitions(
        assets=[raw_books, validate_raw_books, cleaned_books, load_books],
        resources={
            "database": DatabaseResource(connection_string=_DATABASE_URL),
            "path": PathResource(raw_data_dir=_RAW_DATA_DIR),
        },
    )
