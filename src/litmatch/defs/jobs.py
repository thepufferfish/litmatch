"""Centralized job definitions for the LitMatch Dagster pipeline.

All asset jobs are defined here to avoid circular imports and provide
a single source of truth for job configuration.
"""
import dagster as dg

etl_pipeline = dg.define_asset_job(
    name="etl_pipeline",
    selection=dg.AssetSelection.assets(
        "raw_books",
        "validated_books",
        "validation_errors",
        "cleaned_books",
        "load_books",
        "review_embeddings",
        "book_embeddings",
    ),
    description="Full ETL pipeline: extract, validate, transform, load books, and generate embeddings.",
)

crawl_and_load = dg.define_asset_job(
    name="crawl",
    selection=dg.AssetSelection.assets(
        "crawl_books",
    ),
    description=(
        "Trigger Scrapyd crawl"
    ),
)

embedding_pipeline = dg.define_asset_job(
    name="embedding_pipeline",
    selection=dg.AssetSelection.assets("review_embeddings", "book_embeddings"),
    description="Generate review and book embeddings for the recommender system.",
)
