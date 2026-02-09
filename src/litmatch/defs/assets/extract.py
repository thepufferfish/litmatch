"""Extract asset: reads raw JSONL data from the scraper output.

This is the first asset in the ETL pipeline. It reads the books.jsonl file
line by line, parsing each JSON line into a dict.

When used in the crawl_and_load job, this asset depends on crawl_books
to ensure the spider finishes writing books.jsonl before extraction begins.
"""
import json

import dagster as dg

from litmatch.defs.resources.path import PathResource


@dg.asset(
    description="Raw book records extracted from books.jsonl",
    kinds={"python"},
    deps=["crawl_books"],
)
def raw_books(
    context: dg.AssetExecutionContext,
    path: PathResource,
) -> list[dict]:
    """Read and parse the books.jsonl file.

    Each line is a JSON object representing one book with its reviews.
    Malformed lines are logged and skipped.

    This asset depends on crawl_books when used in the crawl_and_load job,
    ensuring the spider completes before extraction begins. In the etl_pipeline
    job (which excludes crawl_books), this asset runs independently.

    Args:
        context: Dagster asset execution context for logging.
        path: PathResource providing the path to books.jsonl.
    """
    filepath = path.books_jsonl_path
    context.log.info(f"Reading JSONL from: {filepath}")

    data: list[dict] = []
    skipped = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                context.log.warning(
                    f"Skipping malformed JSON at line {line_number}: {line.strip()[:100]}"
                )
                skipped += 1

    context.log.info(f"Extracted {len(data)} records ({skipped} skipped)")
    return data
