"""Tests for asset dependency declarations.

Verifies that Dagster asset dependencies are correctly declared so that
the execution order within jobs is deterministic and correct.

The critical bug being addressed: raw_books was missing an explicit
dependency on crawl_books, causing Dagster to execute them in parallel
within the crawl_and_load job. This meant raw_books could try to read
books.jsonl before the spider finished writing it.
"""
import dagster as dg


class TestRawBooksDependsOnCrawlBooks:
    """Verify raw_books declares crawl_books as an upstream dependency.

    In Dagster, asset dependencies can be declared via the deps parameter
    in the @asset decorator. This creates a graph-only dependency that
    ensures execution order without requiring IO manager loads.
    """

    def test_raw_books_asset_deps_include_crawl_books(self) -> None:
        """raw_books must declare crawl_books as an upstream asset dependency.

        This is the core test for the bug fix. Without this dependency,
        the crawl_and_load job can fire raw_books before the spider
        has finished writing books.jsonl.
        """
        from litmatch.defs.assets.extract import raw_books

        raw_books_key = dg.AssetKey("raw_books")
        deps = raw_books.asset_deps[raw_books_key]

        assert dg.AssetKey("crawl_books") in deps, (
            "raw_books must declare crawl_books as an upstream dependency "
            "to prevent parallel execution in the crawl_and_load job."
        )


class TestRawBooksStillFunctional:
    """Verify raw_books still works correctly after adding the dependency.

    With deps=["crawl_books"], raw_books can be materialized independently
    in jobs that don't include crawl_books (like etl_pipeline).
    """

    def test_raw_books_works_without_crawl_books_materialized(
        self, jsonl_file: str
    ) -> None:
        """raw_books should work when materialized without crawl_books.

        This verifies that using deps= instead of a function parameter
        allows raw_books to run in etl_pipeline (which excludes crawl_books).
        """
        import os
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.resources.path import PathResource

        data_dir = os.path.dirname(jsonl_file)

        # Materialize raw_books WITHOUT crawl_books in the asset list
        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        output = result.output_for_node("raw_books")
        assert len(output) == 2  # Two records in fixture

    def test_raw_books_works_with_crawl_books_in_graph(self, jsonl_file: str) -> None:
        """raw_books should work when both assets are in the graph together.

        This verifies behavior in crawl_and_load job where both assets exist.
        """
        import os
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.resources.path import PathResource

        data_dir = os.path.dirname(jsonl_file)

        # Create a mock crawl_books asset
        @dg.asset
        def crawl_books() -> str:
            return "mock-job-id-123"

        result = dg.materialize_to_memory(
            [crawl_books, raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        output = result.output_for_node("raw_books")
        assert len(output) == 2


class TestReviewEmbeddingsInJobs:
    """[HIGH-3] Tests that review_embeddings is included in job definitions.

    The review_embeddings asset must be part of both etl_pipeline and
    crawl_and_load jobs so embeddings are generated automatically as
    part of the standard pipeline runs.
    """

    def test_etl_pipeline_includes_review_embeddings(self) -> None:
        """etl_pipeline job selection must include review_embeddings."""
        from litmatch.defs.jobs import etl_pipeline

        selection_str = str(etl_pipeline.selection)
        assert "review_embeddings" in selection_str, (
            "etl_pipeline must include review_embeddings in its asset selection"
        )

    def test_crawl_and_load_includes_review_embeddings(self) -> None:
        """crawl_and_load job selection must include review_embeddings."""
        from litmatch.defs.jobs import crawl_and_load

        selection_str = str(crawl_and_load.selection)
        assert "review_embeddings" in selection_str, (
            "crawl_and_load must include review_embeddings in its asset selection"
        )

    def test_review_embeddings_after_load_books_in_etl(self) -> None:
        """review_embeddings depends on load_books in the etl_pipeline selection."""
        from litmatch.defs.assets.embedding import review_embeddings

        dep_keys = review_embeddings.asset_deps[review_embeddings.key]
        assert dg.AssetKey("load_books") in dep_keys


class TestEtlPipelineJobUnchanged:
    """Verify that the etl_pipeline job (ETL-only, no crawl) still works.

    The etl_pipeline job does NOT include crawl_books, so raw_books
    must be materializable without crawl_books being present in the graph.
    """

    def test_etl_pipeline_runs_raw_books_without_crawl_books(
        self, jsonl_file: str
    ) -> None:
        """etl_pipeline must run raw_books without crawl_books being materialized.

        This is the critical test ensuring deps= creates a soft dependency
        that doesn't break ETL-only jobs.
        """
        import os
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.assets.validate import validate_raw_books
        from litmatch.defs.assets.transform import cleaned_books
        from litmatch.defs.resources.path import PathResource

        data_dir = os.path.dirname(jsonl_file)

        # Materialize the ETL pipeline assets WITHOUT crawl_books
        result = dg.materialize_to_memory(
            [raw_books, validate_raw_books, cleaned_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success, (
            "etl_pipeline assets must work without crawl_books in the graph"
        )
