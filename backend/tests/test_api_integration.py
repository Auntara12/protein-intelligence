"""
Integration tests for API routes.

Strategy:
  - All external HTTP calls (UniProt, AlphaFold, PDB, ClinVar) are mocked
    using pytest-mock / unittest.mock.patch
  - DB is the in-memory SQLite from conftest.py
  - Tests verify HTTP status codes, response shapes, and caching behavior
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from tests.conftest import MOCK_TP53_DATA


class TestHealthEndpoint:
    """Health check should always return 200."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_shape(self, client):
        response = await client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "version" in data


class TestProteinEndpoint:
    """Tests for GET /api/v1/protein/{gene}"""

    @pytest.mark.asyncio
    async def test_protein_not_found_returns_404(self, client):
        """When UniProt returns nothing, API should 404."""
        with patch(
            "app.api.routes.protein.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.get("/api/v1/protein/FAKEGENE123")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_protein_found_returns_200(self, client):
        """When UniProt returns data, API should return 200 with correct shape."""
        with patch(
            "app.api.routes.protein.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ):
            response = await client.get("/api/v1/protein/TP53")
        assert response.status_code == 200
        data = response.json()
        assert data["gene_name"] == "TP53"
        assert data["uniprot_id"] == "P04637"
        assert "sequence" in data
        assert "domains" in data
        assert isinstance(data["domains"], list)

    @pytest.mark.asyncio
    async def test_protein_cached_on_second_request(self, client):
        """Second request for same gene should be served from DB (cached=True)."""
        with patch(
            "app.api.routes.protein.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ) as mock_fetch:
            # First request: fetches from UniProt
            r1 = await client.get("/api/v1/protein/TP53")
            assert r1.status_code == 200

            # Second request: should hit DB, not UniProt
            r2 = await client.get("/api/v1/protein/TP53")
            assert r2.status_code == 200
            assert r2.json()["cached"] is True

            # UniProt should only have been called once
            assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_gene_name_normalized_to_uppercase(self, client):
        """Lowercase gene name should be normalized."""
        with patch(
            "app.api.routes.protein.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ):
            response = await client.get("/api/v1/protein/tp53")
        assert response.status_code == 200
        assert response.json()["gene_name"] == "TP53"

    @pytest.mark.asyncio
    async def test_protein_sequence_endpoint(self, client):
        """GET /protein/{gene}/sequence should return just the sequence."""
        with patch(
            "app.api.routes.protein.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ):
            # Seed protein first
            await client.get("/api/v1/protein/TP53")
            response = await client.get("/api/v1/protein/TP53/sequence")
        assert response.status_code == 200
        data = response.json()
        assert "sequence" in data
        assert "length" in data


class TestMutationEndpoint:
    """Tests for GET /api/v1/mutation/{gene}/{mutation}"""

    @pytest.mark.asyncio
    async def test_valid_mutation_returns_200(self, client):
        with patch(
            "app.api.routes.mutation.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ), patch(
            "app.api.routes.mutation.fetch_clinvar_variants",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await client.get("/api/v1/mutation/TP53/R175H")
        assert response.status_code == 200
        data = response.json()
        assert data["gene_name"] == "TP53"
        assert data["mutation_str"] == "R175H"
        assert data["parse"]["original_aa"] == "R"
        assert data["parse"]["position"] == 175
        assert data["parse"]["mutated_aa"] == "H"

    @pytest.mark.asyncio
    async def test_invalid_mutation_format_returns_422(self, client):
        """Bad mutation format should return 422 Unprocessable Entity."""
        response = await client.get("/api/v1/mutation/TP53/BADFORMAT")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_mutation_domain_context_populated(self, client):
        """R175H is in the DNA-binding domain (102-292) from our mock data."""
        with patch(
            "app.api.routes.mutation.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ), patch(
            "app.api.routes.mutation.fetch_clinvar_variants",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await client.get("/api/v1/mutation/TP53/R175H")
        data = response.json()
        assert data["domain"] == "DNA-binding domain"

    @pytest.mark.asyncio
    async def test_pathogenic_mutation_flagged(self, client):
        """When ClinVar returns pathogenic, is_known_pathogenic should be True."""
        mock_clinvar = [{
            "variant_id": "12375",
            "clinical_significance": "Pathogenic",
            "disease_name": "Li-Fraumeni syndrome",
            "review_status": "criteria provided",
            "hgvs_expression": "NM_000546.6:c.524G>A",
            "last_evaluated": "2023-01-01",
        }]
        with patch(
            "app.api.routes.mutation.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ), patch(
            "app.api.routes.mutation.fetch_clinvar_variants",
            new_callable=AsyncMock,
            return_value=mock_clinvar,
        ):
            response = await client.get("/api/v1/mutation/TP53/R175H")
        data = response.json()
        assert data["is_known_pathogenic"] is True
        assert len(data["clinvar_data"]) == 1

    @pytest.mark.asyncio
    async def test_mutation_property_changes_present(self, client):
        """All four property change fields should be in the response."""
        with patch(
            "app.api.routes.mutation.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ), patch(
            "app.api.routes.mutation.fetch_clinvar_variants",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await client.get("/api/v1/mutation/TP53/R175H")
        data = response.json()
        assert data["charge_change"] is not None
        assert data["polarity_change"] is not None
        assert data["size_change"] is not None
        assert data["hydrophobicity_change"] is not None
        assert data["predicted_effect"] is not None


class TestAlignmentEndpoint:
    """Tests for GET /api/v1/align/{gene1}/{gene2}"""

    @pytest.mark.asyncio
    async def test_align_two_genes(self, client):
        from tests.conftest import MOCK_BRCA1_SEQUENCE
        mock_brca1 = {**MOCK_TP53_DATA, "gene_name": "BRCA1", "sequence": MOCK_BRCA1_SEQUENCE}

        with patch(
            "app.api.routes.alignment._get_sequence",
            new_callable=AsyncMock,
            side_effect=[MOCK_TP53_DATA["sequence"], MOCK_BRCA1_SEQUENCE],
        ):
            response = await client.get("/api/v1/align/TP53/BRCA1")
        assert response.status_code == 200
        data = response.json()
        assert data["gene1"] == "TP53"
        assert data["gene2"] == "BRCA1"
        assert "score" in data
        assert "identity_pct" in data
        assert 0 <= data["identity_pct"] <= 100
        assert "interpretation" in data
        assert len(data["interpretation"]) > 0

    @pytest.mark.asyncio
    async def test_align_same_gene_returns_400(self, client):
        response = await client.get("/api/v1/align/TP53/TP53")
        assert response.status_code == 400
        assert "itself" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_align_missing_gene_returns_404(self, client):
        with patch(
            "app.api.routes.alignment._get_sequence",
            new_callable=AsyncMock,
            side_effect=[None, "ACDEF"],
        ):
            response = await client.get("/api/v1/align/FAKEGENE/TP53")
        assert response.status_code == 404


class TestBatchEndpoint:
    """Tests for POST /api/v1/batch-analyze"""

    @pytest.mark.asyncio
    async def test_batch_csv_upload_succeeds(self, client):
        csv_content = b"gene,mutation\nTP53,R175H\nBRCA1,M1775R\n"
        with patch(
            "app.api.routes.batch.fetch_protein_from_uniprot",
            new_callable=AsyncMock,
            return_value=MOCK_TP53_DATA,
        ), patch(
            "app.api.routes.batch.fetch_clinvar_variants",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await client.post(
                "/api/v1/batch-analyze",
                files={"file": ("mutations.csv", csv_content, "text/csv")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "results" in data
        assert "processing_time_ms" in data

    @pytest.mark.asyncio
    async def test_batch_rejects_non_csv(self, client):
        response = await client.post(
            "/api/v1/batch-analyze",
            files={"file": ("data.txt", b"not a csv", "text/plain")},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_rejects_missing_columns(self, client):
        bad_csv = b"protein,variant\nTP53,R175H\n"
        response = await client.post(
            "/api/v1/batch-analyze",
            files={"file": ("bad.csv", bad_csv, "text/csv")},
        )
        assert response.status_code == 400
        assert "columns" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_batch_over_limit_rejected(self, client):
        rows = "\n".join(f"TP53,R{i}H" for i in range(1, 52))
        big_csv = f"gene,mutation\n{rows}".encode()
        response = await client.post(
            "/api/v1/batch-analyze",
            files={"file": ("big.csv", big_csv, "text/csv")},
        )
        assert response.status_code == 400
        assert "50" in response.json()["detail"]
