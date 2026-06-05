import httpx
import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.cache import cache_get, cache_set, make_cache_key

logger = logging.getLogger(__name__)

# Amino acid property tables
AA_PROPERTIES = {
    "A": {"name": "Alanine",       "charge": "neutral",  "polarity": "nonpolar", "size": "small",  "hydrophobic": True},
    "R": {"name": "Arginine",      "charge": "positive", "polarity": "polar",    "size": "large",  "hydrophobic": False},
    "N": {"name": "Asparagine",    "charge": "neutral",  "polarity": "polar",    "size": "medium", "hydrophobic": False},
    "D": {"name": "Aspartate",     "charge": "negative", "polarity": "polar",    "size": "small",  "hydrophobic": False},
    "C": {"name": "Cysteine",      "charge": "neutral",  "polarity": "polar",    "size": "small",  "hydrophobic": False},
    "Q": {"name": "Glutamine",     "charge": "neutral",  "polarity": "polar",    "size": "medium", "hydrophobic": False},
    "E": {"name": "Glutamate",     "charge": "negative", "polarity": "polar",    "size": "medium", "hydrophobic": False},
    "G": {"name": "Glycine",       "charge": "neutral",  "polarity": "nonpolar", "size": "tiny",   "hydrophobic": False},
    "H": {"name": "Histidine",     "charge": "positive", "polarity": "polar",    "size": "large",  "hydrophobic": False},
    "I": {"name": "Isoleucine",    "charge": "neutral",  "polarity": "nonpolar", "size": "large",  "hydrophobic": True},
    "L": {"name": "Leucine",       "charge": "neutral",  "polarity": "nonpolar", "size": "large",  "hydrophobic": True},
    "K": {"name": "Lysine",        "charge": "positive", "polarity": "polar",    "size": "large",  "hydrophobic": False},
    "M": {"name": "Methionine",    "charge": "neutral",  "polarity": "nonpolar", "size": "large",  "hydrophobic": True},
    "F": {"name": "Phenylalanine", "charge": "neutral",  "polarity": "nonpolar", "size": "large",  "hydrophobic": True},
    "P": {"name": "Proline",       "charge": "neutral",  "polarity": "nonpolar", "size": "small",  "hydrophobic": False},
    "S": {"name": "Serine",        "charge": "neutral",  "polarity": "polar",    "size": "small",  "hydrophobic": False},
    "T": {"name": "Threonine",     "charge": "neutral",  "polarity": "polar",    "size": "medium", "hydrophobic": False},
    "W": {"name": "Tryptophan",    "charge": "neutral",  "polarity": "nonpolar", "size": "large",  "hydrophobic": True},
    "Y": {"name": "Tyrosine",      "charge": "neutral",  "polarity": "polar",    "size": "large",  "hydrophobic": False},
    "V": {"name": "Valine",        "charge": "neutral",  "polarity": "nonpolar", "size": "medium", "hydrophobic": True},
}


async def fetch_protein_from_uniprot(gene_name: str, organism: str = "human") -> Optional[Dict[str, Any]]:
    """
    Fetch protein data from UniProt REST API.
    Returns structured dict or None if not found.
    """
    cache_key = make_cache_key("uniprot", gene_name, organism)
    cached = await cache_get(cache_key)
    if cached:
        logger.info(f"Cache hit: {cache_key}")
        return {**cached, "cached": True}

    # Build UniProt search query
    organism_tax = "9606" if organism == "human" else organism
    query = f"gene_exact:{gene_name} AND organism_id:{organism_tax} AND reviewed:true"

    params = {
        "query": query,
        "format": "json",
        "fields": ",".join([
            "gene_names", "protein_name", "organism_name",
            "sequence", "length", "cc_function",
            "ft_domain", "ft_region", "ft_motif", "ft_act_site", "ft_binding",
            "cc_disease", "go", "cc_subcellular_location",
            "mass", "accession",
        ]),
        "size": 1,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(settings.UNIPROT_BASE_URL + "/search", params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"UniProt HTTP error for {gene_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"UniProt fetch error for {gene_name}: {e}")
            return None

    results = data.get("results", [])
    if not results:
        # Try broader search without reviewed filter
        params["query"] = f"gene_exact:{gene_name} AND organism_id:{organism_tax}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(settings.UNIPROT_BASE_URL + "/search", params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
            except Exception:
                pass

    if not results:
        logger.warning(f"No UniProt results for gene: {gene_name}")
        return None

    entry = results[0]
    parsed = _parse_uniprot_entry(entry, gene_name)
    await cache_set(cache_key, parsed, ttl=86400)  # 24h for protein data
    return parsed


def _parse_uniprot_entry(entry: Dict, gene_name: str) -> Dict[str, Any]:
    """Parse raw UniProt JSON into clean structured dict."""
    # Accession
    uniprot_id = entry.get("primaryAccession", "")

    # Protein name
    pn = entry.get("proteinDescription", {})
    recommended = pn.get("recommendedName", {})
    protein_name = (
        recommended.get("fullName", {}).get("value")
        or pn.get("submissionNames", [{}])[0].get("fullName", {}).get("value", "")
    )

    # Organism
    organism = entry.get("organism", {}).get("scientificName", "")

    # Sequence
    seq_data = entry.get("sequence", {})
    sequence = seq_data.get("value", "")
    seq_length = seq_data.get("length", len(sequence))

    # Function
    comments = entry.get("comments", [])
    function_summary = ""
    for c in comments:
        if c.get("commentType") == "FUNCTION":
            texts = c.get("texts", [])
            if texts:
                function_summary = texts[0].get("value", "")
                break

    # Domains
    features = entry.get("features", [])
    domains = []
    for f in features:
        if f.get("type") in ("Domain", "Region", "Motif", "Active site", "Binding site"):
            loc = f.get("location", {})
            domains.append({
                "type": f.get("type"),
                "name": f.get("description", ""),
                "start": loc.get("start", {}).get("value"),
                "end": loc.get("end", {}).get("value"),
            })

    # Disease annotations
    diseases = []
    for c in comments:
        if c.get("commentType") == "DISEASE":
            disease = c.get("disease", {})
            diseases.append({
                "name": disease.get("diseaseId", ""),
                "description": disease.get("description", ""),
                "mim_id": disease.get("diseaseCrossReference", {}).get("id", ""),
            })

    # GO terms
    go_terms = []
    for ref in entry.get("uniProtKBCrossReferences", []):
        if ref.get("database") == "GO":
            props = {p["key"]: p["value"] for p in ref.get("properties", [])}
            go_terms.append({
                "id": ref.get("id"),
                "term": props.get("GoTerm", ""),
                "aspect": props.get("GoEvidenceType", ""),
            })

    # Subcellular location
    subcellular = ""
    for c in comments:
        if c.get("commentType") == "SUBCELLULAR LOCATION":
            locs = c.get("subcellularLocations", [])
            if locs:
                loc_val = locs[0].get("location", {}).get("value", "")
                subcellular = loc_val
                break

    # Mass
    mass = seq_data.get("molWeight", None)

    return {
        "gene_name": gene_name.upper(),
        "uniprot_id": uniprot_id,
        "protein_name": protein_name,
        "organism": organism,
        "sequence": sequence,
        "sequence_length": seq_length,
        "function_summary": function_summary,
        "domains": domains,
        "disease_annotations": diseases,
        "go_terms": go_terms[:20],  # cap at 20
        "subcellular_location": subcellular,
        "mass_da": mass,
        "raw_uniprot": entry,
        "cached": False,
    }


def parse_mutation_string(gene: str, mutation: str) -> Dict[str, Any]:
    """
    Parse a mutation string like R175H into components.
    Supports standard HGVS-like protein notation: [AA1][pos][AA2]
    """
    import re

    mutation = mutation.strip().upper()
    pattern = r"^([A-Z*])(\d+)([A-Z*])$"
    match = re.match(pattern, mutation)

    if not match:
        return {
            "raw": mutation,
            "gene": gene.upper(),
            "valid": False,
            "error": f"Invalid mutation format '{mutation}'. Expected format: R175H (original AA, position, mutated AA).",
            "original_aa": "",
            "original_aa_full": "",
            "position": 0,
            "mutated_aa": "",
            "mutated_aa_full": "",
        }

    orig_aa = match.group(1)
    position = int(match.group(2))
    mut_aa = match.group(3)

    orig_props = AA_PROPERTIES.get(orig_aa, {})
    mut_props = AA_PROPERTIES.get(mut_aa, {})

    return {
        "raw": mutation,
        "gene": gene.upper(),
        "original_aa": orig_aa,
        "original_aa_full": orig_props.get("name", orig_aa),
        "position": position,
        "mutated_aa": mut_aa,
        "mutated_aa_full": mut_props.get("name", mut_aa),
        "valid": True,
        "error": None,
    }


def analyze_mutation_properties(orig_aa: str, mut_aa: str, domains: List[Dict], position: int) -> Dict[str, Any]:
    """
    Compute biochemical property changes and domain context for a mutation.
    """
    orig = AA_PROPERTIES.get(orig_aa, {})
    mut = AA_PROPERTIES.get(mut_aa, {})

    # Charge change
    if orig.get("charge") == mut.get("charge"):
        charge_change = f"No change ({orig.get('charge', 'unknown')})"
    else:
        charge_change = f"{orig.get('charge', '?')} → {mut.get('charge', '?')} (potentially disruptive)"

    # Polarity
    if orig.get("polarity") == mut.get("polarity"):
        polarity_change = f"No change ({orig.get('polarity', 'unknown')})"
    else:
        polarity_change = f"{orig.get('polarity', '?')} → {mut.get('polarity', '?')}"

    # Size
    size_order = {"tiny": 0, "small": 1, "medium": 2, "large": 3}
    orig_size = orig.get("size", "medium")
    mut_size = mut.get("size", "medium")
    if orig_size == mut_size:
        size_change = f"No change ({orig_size})"
    elif size_order.get(orig_size, 2) > size_order.get(mut_size, 2):
        size_change = f"{orig_size} → {mut_size} (smaller, potential cavity)"
    else:
        size_change = f"{orig_size} → {mut_size} (larger, potential steric clash)"

    # Hydrophobicity
    if orig.get("hydrophobic") == mut.get("hydrophobic"):
        hydro_change = "No change"
    elif orig.get("hydrophobic"):
        hydro_change = "Hydrophobic → Hydrophilic (may disrupt core packing)"
    else:
        hydro_change = "Hydrophilic → Hydrophobic (may bury charged/polar residue)"

    # Domain location — pick most specific (smallest range), prefer type "Domain" over "Region"
    domain_hit = None
    best_span = None
    best_is_domain_type = False
    for domain in domains:
        start = domain.get("start")
        end = domain.get("end")
        if start and end and start <= position <= end:
            span = end - start
            is_domain_type = (domain.get("type", "").lower() == "domain")
            if (
                best_span is None
                or span < best_span
                or (span == best_span and is_domain_type and not best_is_domain_type)
            ):
                best_span = span
                best_is_domain_type = is_domain_type
                domain_hit = domain.get("name") or domain.get("type", "Unknown domain")

    # Generate predicted effect summary
    issues = []
    if orig.get("charge") != mut.get("charge"):
        issues.append("charge disruption")
    if orig.get("polarity") != mut.get("polarity"):
        issues.append("polarity change")
    if "steric clash" in size_change:
        issues.append("steric clash")
    if "core packing" in hydro_change:
        issues.append("hydrophobic core disruption")

    if not issues:
        predicted_effect = f"{orig_aa}{position}{mut_aa} is a conservative substitution with minimal predicted structural impact."
    else:
        effect_str = ", ".join(issues)
        domain_str = f" within the {domain_hit}" if domain_hit else ""
        predicted_effect = (
            f"{orig_aa}{position}{mut_aa}{domain_str} may cause {effect_str}. "
            f"Substitution of {AA_PROPERTIES.get(orig_aa, {}).get('name', orig_aa)} with "
            f"{AA_PROPERTIES.get(mut_aa, {}).get('name', mut_aa)} alters local protein chemistry."
        )

    return {
        "charge_change": charge_change,
        "polarity_change": polarity_change,
        "size_change": size_change,
        "hydrophobicity_change": hydro_change,
        "domain": domain_hit,
        "predicted_effect": predicted_effect,
        "analysis_details": {
            "original_properties": orig,
            "mutated_properties": mut,
        },
    }
