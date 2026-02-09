"""Embedding model resource for the Dagster pipeline.

Wraps a sentence-transformers model for generating text embeddings.
The model is lazily loaded on first use and cached for the lifetime
of the resource (i.e., the Dagster code server process).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import dagster as dg
from pydantic import PrivateAttr

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


# Vetted model identifiers that may be loaded by SentenceTransformer.
# Any model not in this set will be rejected to prevent arbitrary code
# execution from untrusted HuggingFace Hub models.
# NOTE: Only models with 384 dimensions are supported until Phase 2 adds
# configurable vector dimensions to the database schema (Vector(384) hardcoded).
_ALLOWED_MODELS: frozenset[str] = frozenset({
    "all-MiniLM-L6-v2",  # 384 dimensions
})

# Known model dimensions for dimension lookup without loading the model.
_MODEL_DIMENSIONS: dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
}

_DEFAULT_DIMENSIONS = 384


class EmbeddingModelResource(dg.ConfigurableResource):
    """Dagster resource for sentence-transformer text encoding.

    Lazily loads the sentence-transformers model on first call to
    encode(). The model is cached in a Pydantic PrivateAttr so it
    persists across asset materializations within the same code server.

    Args:
        model_name: HuggingFace model identifier for sentence-transformers.
    """

    model_name: str = "all-MiniLM-L6-v2"
    _model: SentenceTransformer | None = PrivateAttr(default=None)

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensionality for the configured model."""
        return _MODEL_DIMENSIONS.get(self.model_name, _DEFAULT_DIMENSIONS)

    def _get_model(self) -> SentenceTransformer:
        """Lazily load and cache the sentence-transformers model.

        Raises:
            ValueError: If model_name is not in the _ALLOWED_MODELS set.
        """
        if self._model is None:
            if self.model_name not in _ALLOWED_MODELS:
                raise ValueError(
                    f"Model '{self.model_name}' is not in the allowed models list. "
                    f"Allowed models: {sorted(_ALLOWED_MODELS)}"
                )
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts into embedding vectors.

        Args:
            texts: List of text strings to encode.

        Returns:
            List of embedding vectors as Python float lists.
        """
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False, batch_size=64)
        return embeddings.tolist()
