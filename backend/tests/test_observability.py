"""
Unit tests for metrics collection and path normalization.

These are pure unit tests — no DB, no Redis, no network.
They verify the path normalization logic that prevents Prometheus
cardinality explosion, and that metric counters increment correctly.
"""
import pytest
from app.api.observability import _normalize_path
from app.core.metrics import (
    REQUEST_COUNT, CACHE_HITS, CACHE_MISSES,
    record_cache_hit, record_cache_miss,
)


class TestPathNormalization:
    """
    Tests for _normalize_path().

    Why this matters: without normalization, every unique gene creates
    a new Prometheus label combination. 1000 genes = 1000 label sets =
    cardinality explosion that degrades Prometheus performance.

    With normalization: /api/v1/protein/TP53 and /api/v1/protein/BRCA1
    both map to /api/v1/protein/{gene} — one label set for all genes.
    """

    def test_protein_endpoint_normalized(self):
        result = _normalize_path("/api/v1/protein/TP53")
        assert result == "/api/v1/protein/{gene}"

    def test_mutation_endpoint_normalized(self):
        result = _normalize_path("/api/v1/mutation/TP53/R175H")
        assert result == "/api/v1/mutation/{gene}/{mutation}"

    def test_structure_endpoint_normalized(self):
        result = _normalize_path("/api/v1/structure/BRCA1")
        assert result == "/api/v1/structure/{gene}"

    def test_similar_endpoint_normalized(self):
        result = _normalize_path("/api/v1/similar/EGFR")
        assert result == "/api/v1/similar/{gene}"

    def test_align_endpoint_normalized(self):
        result = _normalize_path("/api/v1/align/TP53/BRCA1")
        assert result == "/api/v1/align/{gene1}/{gene2}"

    def test_compare_endpoint_normalized(self):
        result = _normalize_path("/api/v1/compare/TP53/TP63")
        assert result == "/api/v1/compare/{gene1}/{gene2}"

    def test_static_paths_unchanged(self):
        """Paths with no dynamic segments should pass through unchanged."""
        assert _normalize_path("/api/v1/health") == "/api/v1/health"
        assert _normalize_path("/api/v1/metrics") == "/api/v1/metrics"
        assert _normalize_path("/docs") == "/docs"

    def test_batch_path_unchanged(self):
        assert _normalize_path("/api/v1/batch-analyze") == "/api/v1/batch-analyze"

    def test_different_genes_same_label(self):
        """TP53 and BRCA1 should produce identical normalized paths."""
        assert _normalize_path("/api/v1/protein/TP53") == _normalize_path("/api/v1/protein/BRCA1")
        assert _normalize_path("/api/v1/similar/EGFR") == _normalize_path("/api/v1/similar/KRAS")

    def test_different_mutations_same_label(self):
        assert (
            _normalize_path("/api/v1/mutation/TP53/R175H")
            == _normalize_path("/api/v1/mutation/BRCA1/M1775R")
        )

    def test_embed_status_normalized(self):
        """Fix 2: /api/v1/embed/status/{job_id} must normalize correctly."""
        result = _normalize_path("/api/v1/embed/status/abc123def456")
        assert result == "/api/v1/embed/status/{job_id}"

    def test_embed_status_different_ids_same_label(self):
        assert (
            _normalize_path("/api/v1/embed/status/abc123")
            == _normalize_path("/api/v1/embed/status/xyz789")
        )


class TestCacheMetrics:
    """Tests that cache hit/miss counters increment correctly."""

    def test_cache_hit_increments_counter(self):
        before = CACHE_HITS.labels(key_prefix="UNIPROT")._value.get()
        record_cache_hit("pip:UNIPROT:TP53:HUMAN")
        after = CACHE_HITS.labels(key_prefix="UNIPROT")._value.get()
        assert after == before + 1

    def test_cache_miss_increments_counter(self):
        before = CACHE_MISSES.labels(key_prefix="ALPHAFOLD")._value.get()
        record_cache_miss("pip:ALPHAFOLD:P04637")
        after = CACHE_MISSES.labels(key_prefix="ALPHAFOLD")._value.get()
        assert after == before + 1

    def test_cache_hit_uses_second_segment_as_prefix(self):
        """Key format is pip:PREFIX:... so prefix is always the second segment."""
        before = CACHE_HITS.labels(key_prefix="CLINVAR")._value.get()
        record_cache_hit("pip:CLINVAR:TP53:R175H")
        after = CACHE_HITS.labels(key_prefix="CLINVAR")._value.get()
        assert after == before + 1

    def test_cache_hit_and_miss_are_independent(self):
        """Hits and misses for same prefix are tracked separately."""
        hits_before = CACHE_HITS.labels(key_prefix="PDB")._value.get()
        misses_before = CACHE_MISSES.labels(key_prefix="PDB")._value.get()

        record_cache_hit("pip:PDB:TP53")
        record_cache_hit("pip:PDB:BRCA1")
        record_cache_miss("pip:PDB:FAKEGENE")

        hits_after = CACHE_HITS.labels(key_prefix="PDB")._value.get()
        misses_after = CACHE_MISSES.labels(key_prefix="PDB")._value.get()

        assert hits_after == hits_before + 2
        assert misses_after == misses_before + 1


class TestMetricsSummary:
    """
    Tests that get_metrics_summary() returns correct values.
    Fix 1: verifies the _sum_counter helper correctly reads prometheus-client
    sample names (which append _total internally).
    """

    def test_summary_returns_required_keys(self):
        from app.core.metrics import get_metrics_summary
        summary = get_metrics_summary()
        required = {
            "total_requests", "total_errors", "error_rate_pct",
            "cache_hits", "cache_misses", "cache_hit_rate_pct", "active_requests"
        }
        assert required.issubset(set(summary.keys()))

    def test_summary_values_are_numeric(self):
        from app.core.metrics import get_metrics_summary
        summary = get_metrics_summary()
        for key, value in summary.items():
            assert isinstance(value, (int, float)), f"{key} is not numeric: {value}"

    def test_cache_hit_rate_reflects_actual_increments(self):
        """
        After recording known hits and misses, the summary should
        reflect them correctly. This is the core regression test for Fix 1.
        """
        from app.core.metrics import get_metrics_summary, record_cache_hit, record_cache_miss

        before = get_metrics_summary()
        hits_before = before["cache_hits"]
        misses_before = before["cache_misses"]

        record_cache_hit("pip:UNIPROT:TP53")
        record_cache_hit("pip:UNIPROT:BRCA1")
        record_cache_miss("pip:UNIPROT:KRAS")

        after = get_metrics_summary()
        assert after["cache_hits"] == hits_before + 2
        assert after["cache_misses"] == misses_before + 1

    def test_error_rate_is_between_0_and_100(self):
        from app.core.metrics import get_metrics_summary
        summary = get_metrics_summary()
        assert 0.0 <= summary["error_rate_pct"] <= 100.0

    def test_cache_hit_rate_is_between_0_and_100(self):
        from app.core.metrics import get_metrics_summary
        summary = get_metrics_summary()
        assert 0.0 <= summary["cache_hit_rate_pct"] <= 100.0

    def test_active_requests_is_non_negative(self):
        from app.core.metrics import get_metrics_summary
        summary = get_metrics_summary()
        assert summary["active_requests"] >= 0
