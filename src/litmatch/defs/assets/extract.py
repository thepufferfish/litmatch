"""Extract asset: reads raw JSONL data from the scraper output.

This is the first asset in the pipeline. It reads the books.jsonl file
line by line, parsing each JSON line into a dict.
"""
import json

import dagster as dg

from litmatch.defs.resources.path import PathResource


@dg.asset(
    description="Raw book records extracted from books.jsonl",
    kinds={"python"},
)
def raw_books(
    context: dg.AssetExecutionContext,
    path: PathResource,
) -> list[dict]:
    """Read and parse the books.jsonl file.

    Each line is a JSON object representing one book with its reviews.
    Malformed lines are logged and skipped.
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
