"""Scrapyd resource for triggering scraper runs (future use).

Currently a placeholder for Phase 2 of the pipeline where we may want
to trigger scraper runs from within Dagster.
"""
import dagster as dg


class ScrapydResource(dg.ConfigurableResource):
    """Dagster resource for Scrapyd spider management.

    Configures the Scrapyd API endpoint for scheduling and
    monitoring spider runs.
    """

    base_url: str = "http://localhost:6800"
    project: str = "bookmarks"
