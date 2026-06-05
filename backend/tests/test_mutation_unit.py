"""
Unit tests for mutation parsing and biochemical analysis.

These tests cover pure functions with no external dependencies.
They run in milliseconds and test the core algorithmic logic.
"""
import pytest
from app.services.uniprot_service import (
    parse_mutation_string,
    analyze_mutation_properties,
    AA_PROPERTIES,
)


class TestMutationParser:
    """Tests for parse_mutation_string()"""

    def test_valid_standard_mutation(self):
        result = parse_mutation_string("TP53", "R175H")
        assert result["valid"] is True
        assert result["gene"] == "TP53"
        assert result["original_aa"] == "R"
        assert result["position"] == 175
        assert result["mutated_aa"] == "H"
        assert result["original_aa_full"] == "Arginine"
        assert result["mutated_aa_full"] == "Histidine"
        assert result["error"] is None

    def test_valid_mutation_lowercased_input(self):
        """Parser should normalize to uppercase."""
        result = parse_mutation_string("tp53", "r175h")
        assert result["valid"] is True
        assert result["gene"] == "TP53"
        assert result["original_aa"] == "R"

    def test_valid_mutation_single_digit_position(self):
        result = parse_mutation_string("BRCA1", "M1R")
        assert result["valid"] is True
        assert result["position"] == 1

    def test_valid_mutation_large_position(self):
        result = parse_mutation_string("TTN", "G34170A")
        assert result["valid"] is True
        assert result["position"] == 34170

    def test_invalid_mutation_no_position(self):
        result = parse_mutation_string("TP53", "RH")
        assert result["valid"] is False
        assert result["error"] is not None
        assert "format" in result["error"].lower()

    def test_invalid_mutation_only_position(self):
        result = parse_mutation_string("TP53", "175")
        assert result["valid"] is False

    def test_invalid_mutation_reversed_format(self):
        """175RH should fail — position must be between the two AAs."""
        result = parse_mutation_string("TP53", "175RH")
        assert result["valid"] is False

    def test_invalid_mutation_empty_string(self):
        result = parse_mutation_string("TP53", "")
        assert result["valid"] is False

    def test_invalid_mutation_special_characters(self):
        result = parse_mutation_string("TP53", "R175*")
        # * is a stop codon — currently not in our AA table but valid HGVS
        # The parser regex accepts * as a valid AA symbol
        assert result["valid"] is True
        assert result["mutated_aa"] == "*"

    def test_gene_normalized_to_uppercase(self):
        result = parse_mutation_string("brca1", "M1775R")
        assert result["gene"] == "BRCA1"

    @pytest.mark.parametrize("mutation,expected_orig,expected_pos,expected_mut", [
        ("R175H", "R", 175, "H"),
        ("G12D", "G", 12, "D"),
        ("L858R", "L", 858, "R"),
        ("M1775R", "M", 1775, "R"),
        ("V600E", "V", 600, "E"),
    ])
    def test_known_cancer_mutations_parse_correctly(
        self, mutation, expected_orig, expected_pos, expected_mut
    ):
        """Regression test for well-known oncogenic mutations."""
        result = parse_mutation_string("GENE", mutation)
        assert result["valid"] is True
        assert result["original_aa"] == expected_orig
        assert result["position"] == expected_pos
        assert result["mutated_aa"] == expected_mut


class TestAminoAcidProperties:
    """Tests for the AA_PROPERTIES lookup table."""

    def test_all_20_standard_amino_acids_present(self):
        standard_aas = set("ACDEFGHIKLMNPQRSTVWY")
        assert standard_aas.issubset(set(AA_PROPERTIES.keys()))

    def test_arginine_is_positive(self):
        assert AA_PROPERTIES["R"]["charge"] == "positive"

    def test_glutamate_is_negative(self):
        assert AA_PROPERTIES["E"]["charge"] == "negative"

    def test_alanine_is_nonpolar(self):
        assert AA_PROPERTIES["A"]["polarity"] == "nonpolar"

    def test_serine_is_polar(self):
        assert AA_PROPERTIES["S"]["polarity"] == "polar"

    def test_glycine_is_tiny(self):
        assert AA_PROPERTIES["G"]["size"] == "tiny"

    def test_tryptophan_is_large(self):
        assert AA_PROPERTIES["W"]["size"] == "large"

    def test_leucine_is_hydrophobic(self):
        assert AA_PROPERTIES["L"]["hydrophobic"] is True

    def test_lysine_is_not_hydrophobic(self):
        assert AA_PROPERTIES["K"]["hydrophobic"] is False

    def test_all_entries_have_required_fields(self):
        required = {"name", "charge", "polarity", "size", "hydrophobic"}
        for aa, props in AA_PROPERTIES.items():
            missing = required - set(props.keys())
            assert not missing, f"AA {aa} missing fields: {missing}"


class TestMutationPropertyAnalysis:
    """Tests for analyze_mutation_properties()"""

    def test_tp53_r175h_charge_change(self):
        """R175H: Arginine (positive) → Histidine (positive). Both positive."""
        result = analyze_mutation_properties("R", "H", [], 175)
        # Both R and H are positive charge — no charge change
        assert "no change" in result["charge_change"].lower()

    def test_charge_disrupting_mutation(self):
        """E → K: negative → positive — clearly disruptive."""
        result = analyze_mutation_properties("E", "K", [], 10)
        assert "negative" in result["charge_change"].lower()
        assert "positive" in result["charge_change"].lower()
        assert "disruptive" in result["charge_change"].lower()

    def test_conservative_substitution_detected(self):
        """L → I: both large, nonpolar, hydrophobic — conservative."""
        result = analyze_mutation_properties("L", "I", [], 50)
        assert "no change" in result["charge_change"].lower()
        assert "no change" in result["polarity_change"].lower()
        assert "no change" in result["size_change"].lower()
        assert "minimal" in result["predicted_effect"].lower()

    def test_domain_context_identified(self):
        """Mutation at position 150 should be found within the test domain."""
        domains = [
            {"type": "Domain", "name": "DNA-binding domain", "start": 102, "end": 292}
        ]
        result = analyze_mutation_properties("R", "H", domains, 150)
        assert result["domain"] == "DNA-binding domain"

    def test_mutation_outside_domain_returns_none(self):
        domains = [
            {"type": "Domain", "name": "DNA-binding domain", "start": 102, "end": 292}
        ]
        result = analyze_mutation_properties("R", "H", domains, 300)
        assert result["domain"] is None

    def test_empty_domains_handled_gracefully(self):
        result = analyze_mutation_properties("R", "H", [], 175)
        assert result["domain"] is None
        assert result["predicted_effect"] is not None

    def test_size_increase_detected(self):
        """G → W: tiny → large — steric clash."""
        result = analyze_mutation_properties("G", "W", [], 10)
        assert "steric clash" in result["size_change"].lower()

    def test_size_decrease_detected(self):
        """W → G: large → tiny — potential cavity."""
        result = analyze_mutation_properties("W", "G", [], 10)
        assert "cavity" in result["size_change"].lower()

    def test_hydrophobic_to_hydrophilic(self):
        """L → E: hydrophobic → hydrophilic — disrupts core packing."""
        result = analyze_mutation_properties("L", "E", [], 30)
        assert "core packing" in result["hydrophobicity_change"].lower()

    def test_analysis_always_returns_predicted_effect(self):
        """predicted_effect must always be a non-empty string."""
        for aa1 in "ACDEFGHIKLMNPQRSTVWY":
            for aa2 in "ACDEFGHIKLMNPQRSTVWY":
                result = analyze_mutation_properties(aa1, aa2, [], 10)
                assert isinstance(result["predicted_effect"], str)
                assert len(result["predicted_effect"]) > 0
