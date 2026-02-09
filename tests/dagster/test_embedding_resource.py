"""Unit tests for the EmbeddingModelResource.

Tests the Dagster resource that wraps sentence-transformers
for generating text embeddings. All tests use mocked models
to avoid loading the actual ML model (which is ~80 MB).
"""
from unittest.mock import MagicMock, patch

import dagster as dg
import numpy as np
import pytest


class TestEmbeddingModelResourceDefinition:
    """Tests that EmbeddingModelResource is properly defined as a Dagster resource."""

    def test_is_configurable_resource(self) -> None:
        """EmbeddingModelResource should be a Dagster ConfigurableResource."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        assert issubclass(EmbeddingModelResource, dg.ConfigurableResource)

    def test_default_model_name(self) -> None:
        """Default model_name should be all-MiniLM-L6-v2."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()
        assert resource.model_name == "all-MiniLM-L6-v2"

    def test_custom_model_name(self) -> None:
        """model_name should be configurable."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource(model_name="all-mpnet-base-v2")
        assert resource.model_name == "all-mpnet-base-v2"

    def test_dimensions_for_default_model(self) -> None:
        """Default model should report 384 dimensions."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()
        assert resource.dimensions == 384

    def test_dimensions_for_mpnet_model(self) -> None:
        """all-mpnet-base-v2 should report 768 dimensions."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource(model_name="all-mpnet-base-v2")
        assert resource.dimensions == 768

    def test_dimensions_for_unknown_model_defaults_to_384(self) -> None:
        """Unknown model names should default to 384 dimensions."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource(model_name="unknown-model")
        assert resource.dimensions == 384


class TestEmbeddingModelResourceEncode:
    """Tests for the encode method that generates embeddings from text."""

    def test_encode_returns_list_of_lists(self) -> None:
        """encode() should return a list of float lists matching input length."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()

        fake_embeddings = np.random.RandomState(42).rand(2, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ):
            result = resource.encode(["hello world", "test text"])

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, list) for r in result)
        assert all(len(r) == 384 for r in result)

    def test_encode_calls_model_with_correct_params(self) -> None:
        """encode() should pass texts and batch_size to the underlying model."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()

        fake_embeddings = np.random.RandomState(42).rand(1, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ):
            resource.encode(["test text"])

        mock_model.encode.assert_called_once_with(
            ["test text"],
            show_progress_bar=False,
            batch_size=64,
        )

    def test_encode_single_text(self) -> None:
        """encode() should handle a single text input."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()

        fake_embeddings = np.random.RandomState(42).rand(1, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ):
            result = resource.encode(["single text"])

        assert len(result) == 1
        assert len(result[0]) == 384

    def test_encode_empty_list_returns_empty(self) -> None:
        """encode() with empty input should return empty list."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()

        fake_embeddings = np.array([]).reshape(0, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ):
            result = resource.encode([])

        assert result == []

    def test_model_loaded_lazily(self) -> None:
        """The underlying SentenceTransformer should not be loaded at init time."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        with patch(
            "sentence_transformers.SentenceTransformer",
        ) as mock_cls:
            resource = EmbeddingModelResource()
            # At this point the model should NOT have been loaded
            mock_cls.assert_not_called()

    def test_model_loaded_on_first_encode(self) -> None:
        """The model should be loaded on the first call to encode()."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()

        fake_embeddings = np.random.RandomState(42).rand(1, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ) as mock_cls:
            resource.encode(["test"])
            mock_cls.assert_called_once_with("all-MiniLM-L6-v2")

    def test_model_cached_across_calls(self) -> None:
        """The model should be loaded once and reused across encode() calls."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()

        fake_embeddings = np.random.RandomState(42).rand(1, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ) as mock_cls:
            resource.encode(["first call"])
            resource.encode(["second call"])
            # SentenceTransformer constructor should only be called once
            mock_cls.assert_called_once()
            # But encode should be called twice
            assert mock_model.encode.call_count == 2

    def test_encode_returns_float_values(self) -> None:
        """All values in returned embeddings should be Python floats."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource()

        fake_embeddings = np.array([[0.1, 0.2, 0.3] + [0.0] * 381]).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ):
            result = resource.encode(["test"])

        # Verify values are Python floats (not numpy types)
        assert all(isinstance(v, float) for v in result[0])

    # Test removed: all-mpnet-base-v2 (768-dim) is not in the allowlist
    # until Phase 2 adds support for configurable vector dimensions in the schema


class TestModelAllowlist:
    """[H-1] Tests for model allowlist to prevent remote code execution.

    SentenceTransformer can load arbitrary models from HuggingFace Hub,
    which could execute untrusted code. The allowlist restricts loading
    to vetted model identifiers only.
    """

    def test_allowed_models_constant_exists(self) -> None:
        """An _ALLOWED_MODELS set should be defined in the module."""
        from litmatch.defs.resources.embedding_model import _ALLOWED_MODELS

        assert isinstance(_ALLOWED_MODELS, frozenset)
        assert len(_ALLOWED_MODELS) >= 1  # At least one model supported

    def test_default_model_is_in_allowlist(self) -> None:
        """The default model all-MiniLM-L6-v2 must be in the allowlist."""
        from litmatch.defs.resources.embedding_model import _ALLOWED_MODELS

        assert "all-MiniLM-L6-v2" in _ALLOWED_MODELS

    # Test removed: all-mpnet-base-v2 is not in allowlist until Phase 2
    # adds support for configurable vector dimensions in the database schema

    def test_allowed_model_loads_successfully(self) -> None:
        """An allowed model should load without raising."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource(model_name="all-MiniLM-L6-v2")

        fake_embeddings = np.random.RandomState(42).rand(1, 384).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ):
            result = resource.encode(["test"])

        assert len(result) == 1

    def test_disallowed_model_raises_valueerror(self) -> None:
        """A model not in the allowlist should raise ValueError on load."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource(model_name="malicious/evil-model")

        with pytest.raises(ValueError, match="not in the allowed"):
            resource._get_model()

    def test_disallowed_model_encode_raises_valueerror(self) -> None:
        """encode() with disallowed model should raise ValueError."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource(model_name="attacker/backdoor-model")

        with pytest.raises(ValueError, match="not in the allowed"):
            resource.encode(["test"])

    def test_disallowed_model_never_calls_sentence_transformer(self) -> None:
        """A disallowed model must be rejected before SentenceTransformer is called."""
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        resource = EmbeddingModelResource(model_name="evil-model")

        with patch(
            "sentence_transformers.SentenceTransformer",
        ) as mock_cls:
            with pytest.raises(ValueError):
                resource._get_model()
            mock_cls.assert_not_called()
