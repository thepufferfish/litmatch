import os
import json

from typing import List, Dict

import dagster as dg

from backend.db.models import Book

RAW_DATA_DIR = '/home/framework/.local/share/containers/storage/volumes/litmatch_shared_scraper_output/_data/raw'

@dg.asset
def extract(context: dg.AssetExecutionContext) -> List[Dict]:

    fn = os.path.join(RAW_DATA_DIR, 'books.jsonl')
    if not os.path.exists(fn):
            context.log.error(f'Raw data path does not exist: {fn}')

    data = []
    with open(fn, 'r', encoding='utf-8') as file:
        for line_number, line in enumerate(file, start=1):
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                context.log.error(f'Error parsing line {line_number}: {line.strip()}')
    return data

@dg.asset
def load(context: dg.AssetExecutionContext) -> None:
    pass