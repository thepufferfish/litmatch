"""Unit tests for _compute_weighted_embedding in recommendations.py.

Tests cover:
- Pure 384-dim input (regression)
- Pure 1152-dim input (regression)
- Mixed 384-dim and 1152-dim input (the migration-period bug)
- Filtering to majority dimension when mixed
- All None embeddings returns None
- All neutral (2-star, weight=0) ratings returns None
"""

import pytest

from backend.app.recommendations import _compute_weighted_embedding


class TestComputeWeightedEmbeddingHomogeneous:
    """Regression tests: pure same-dimension input must still work correctly."""

    def test_all_same_dim_384_computes_correctly(self):
        """Pure 384-dim embeddings compute the correct weighted average."""
        dim = 384
        e1 = [1.0] * dim
        e2 = [3.0] * dim
        # rating 5 -> weight +3, rating 3 -> weight +1
        pairs = [(5, e1), (3, e2)]
        result = _compute_weighted_embedding(pairs)

        assert result is not None
        assert len(result) == dim
        # weight 3*e1 + 1*e2 / (3+1) = (3 + 3) / 4 = 1.5
        assert result[0] == pytest.approx(1.5)

    def test_all_same_dim_1152_computes_correctly(self):
        """Pure 1152-dim embeddings compute the correct weighted average."""
        dim = 1152
        e1 = [2.0] * dim
        e2 = [4.0] * dim
        # rating 5 -> weight +3, rating 4 -> weight +2
        pairs = [(5, e1), (4, e2)]
        result = _compute_weighted_embedding(pairs)

        assert result is not None
        assert len(result) == dim
        # (3*2 + 2*4) / (3+2) = (6+8)/5 = 14/5 = 2.8
        assert result[0] == pytest.approx(2.8)

    def test_single_positive_rating_returns_embedding(self):
        """A single positively-rated book returns its embedding unchanged."""
        dim = 384
        e = [0.5] * dim
        pairs = [(4, e)]  # weight = +2
        result = _compute_weighted_embedding(pairs)

        assert result is not None
        assert len(result) == dim
        assert result[0] == pytest.approx(0.5)

    def test_single_negative_rating_returns_negated_embedding(self):
        """A single 1-star book returns negated embedding (weight = -1)."""
        dim = 384
        e = [0.5] * dim
        pairs = [(1, e)]  # weight = -1
        result = _compute_weighted_embedding(pairs)

        assert result is not None
        assert len(result) == dim
        # (-1 * 0.5) / abs(-1) = -0.5
        assert result[0] == pytest.approx(-0.5)


class TestComputeWeightedEmbeddingEdgeCases:
    """Edge cases: empty input, all-None, all-neutral."""

    def test_empty_input_returns_none(self):
        """Empty list returns None."""
        assert _compute_weighted_embedding([]) is None

    def test_all_none_embeddings_returns_none(self):
        """All None embeddings should return None."""
        pairs = [(5, None), (4, None), (3, None)]
        assert _compute_weighted_embedding(pairs) is None

    def test_all_neutral_ratings_returns_none(self):
        """All 2-star ratings (weight=0) should return None."""
        dim = 384
        e = [1.0] * dim
        pairs = [(2, e), (2, e), (2, e)]
        assert _compute_weighted_embedding(pairs) is None

    def test_mix_of_none_and_neutral_returns_none(self):
        """Combination of None embeddings and 2-star ratings returns None."""
        dim = 384
        e = [1.0] * dim
        pairs = [(2, e), (5, None), (2, e)]
        assert _compute_weighted_embedding(pairs) is None


class TestComputeWeightedEmbeddingMixedDimensions:
    """Tests for mixed-dimension input (the migration-period bug fix)."""

    def test_mixed_dimensions_does_not_raise_index_error(self):
        """Mixed 1152-dim and 384-dim embeddings must not raise IndexError.

        Before the fix, if first embedding was 1152-dim and subsequent
        embeddings were 384-dim, accessing index >= 384 would raise IndexError.
        """
        dim_large = 1152
        dim_small = 384

        e_large = [1.0] * dim_large
        e_small = [2.0] * dim_small

        # First is large, second is small -- the classic IndexError scenario
        pairs = [(5, e_large), (4, e_small)]

        # Must not raise
        result = _compute_weighted_embedding(pairs)
        assert result is not None

    def test_mixed_dimensions_returns_majority_dimension(self):
        """When mixed, result uses the majority dimension.

        Two 1152-dim embeddings vs one 384-dim: majority is 1152.
        """
        dim_large = 1152
        dim_small = 384

        e_large_1 = [1.0] * dim_large
        e_large_2 = [3.0] * dim_large
        e_small = [99.0] * dim_small  # Should be filtered out

        # 2 large (majority) vs 1 small
        pairs = [(5, e_large_1), (4, e_large_2), (5, e_small)]

        result = _compute_weighted_embedding(pairs)
        assert result is not None
        assert len(result) == dim_large

    def test_mixed_dimensions_filters_to_majority_correctly(self):
        """Filters to majority dimension and computes the correct weighted average.

        Majority is 1152-dim (2 embeddings vs 1 of 384-dim).
        The 384-dim embedding should be dropped.
        """
        dim_large = 1152
        dim_small = 384

        e_large_1 = [2.0] * dim_large  # rating 5 -> weight +3
        e_large_2 = [4.0] * dim_large  # rating 3 -> weight +1
        e_small = [99.0] * dim_small   # rating 5, but filtered out

        pairs = [(5, e_large_1), (3, e_large_2), (5, e_small)]

        result = _compute_weighted_embedding(pairs)

        assert result is not None
        assert len(result) == dim_large
        # Only e_large_1 (w=3) and e_large_2 (w=1) kept
        # (3*2 + 1*4) / (3+1) = 10/4 = 2.5
        assert result[0] == pytest.approx(2.5)

    def test_mixed_dimensions_small_is_majority(self):
        """When 384-dim is majority (more of them), use 384-dim.

        Two 384-dim embeddings vs one 1152-dim.
        """
        dim_large = 1152
        dim_small = 384

        e_small_1 = [1.0] * dim_small  # rating 5 -> weight +3
        e_small_2 = [3.0] * dim_small  # rating 3 -> weight +1
        e_large = [99.0] * dim_large   # rating 5, but filtered out (minority)

        pairs = [(5, e_small_1), (3, e_small_2), (5, e_large)]

        result = _compute_weighted_embedding(pairs)

        assert result is not None
        assert len(result) == dim_small
        # Only e_small_1 (w=3) and e_small_2 (w=1) kept
        # (3*1 + 1*3) / (3+1) = 6/4 = 1.5
        assert result[0] == pytest.approx(1.5)

    def test_mixed_all_filtered_pairs_have_same_dim_after_filtering(self):
        """After dimension filtering, all remaining pairs share the same dimension."""
        dim_large = 1152
        dim_small = 384

        # 3 large vs 2 small -- majority is large
        pairs = [
            (5, [1.0] * dim_large),
            (4, [2.0] * dim_large),
            (5, [3.0] * dim_large),
            (4, [99.0] * dim_small),
            (3, [99.0] * dim_small),
        ]

        result = _compute_weighted_embedding(pairs)
        assert result is not None
        assert len(result) == dim_large

    def test_tie_in_dimension_count_uses_first_encountered(self):
        """When two dimensions are tied, the result still succeeds.

        The most_common(1) call returns a consistent winner even in a tie.
        """
        dim_large = 1152
        dim_small = 384

        # 1 large, 1 small -- tied
        pairs = [
            (5, [2.0] * dim_large),
            (4, [99.0] * dim_small),
        ]

        result = _compute_weighted_embedding(pairs)
        # Should return a result without raising, length is one of the two dims
        assert result is not None
        assert len(result) in (dim_large, dim_small)
