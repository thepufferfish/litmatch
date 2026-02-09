"""Centralized job definitions for the LitMatch Dagster pipeline.

All asset jobs are defined here to avoid circular imports and provide
a single source of truth for job configuration.
"""
import dagster as dg

etl_pipeline = dg.define_asset_job(
    name="etl_pipeline",
    selection=dg.AssetSelection.assets(
        "raw_books", "validated_books", "validation_errors", "cleaned_books", "load_books"
    ),
    description="Full ETL pipeline: extract, validate, transform, and load books.",
)

crawl_and_load = dg.define_asset_job(
    name="crawl_and_load",
    selection=dg.AssetSelection.assets(
        "crawl_books",
        "raw_books",
        "validated_books",
        "validation_errors",
        "cleaned_books",
        "load_books",
    ),
    description=(
        "Full crawl-and-load pipeline: trigger Scrapyd crawl, "
        "then extract, validate, transform, and load books."
    ),
)
