import httpx
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.cache import cache_get, cache_set, make_cache_key

logger = logging.getLogger(__name__)


async def fetch_clinvar_variants(gene_name: str, mutation_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Query NCBI ClinVar for variants associated with a gene (and optionally a specific mutation).
    Uses the NCBI Entrez eSearch + eSummary pipeline.
    """
    cache_key = make_cache_key("clinvar", gene_name, mutation_str or "all")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Build search term
    if mutation_str:
        search_term = f"{gene_name}[gene] AND {mutation_str}"
    else:
        search_term = f"{gene_name}[gene] AND (pathogenic[clinical_significance] OR likely_pathogenic[clinical_significance])"

    params = {
        "db": "clinvar",
        "term": search_term,
        "retmax": 10,
        "retmode": "json",
        "usehistory": "y",
    }
    if settings.NCBI_API_KEY:
        params["api_key"] = settings.NCBI_API_KEY

    variant_ids = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{settings.CLINVAR_BASE_URL}/esearch.fcgi", params=params)
            resp.raise_for_status()
            data = resp.json()
            variant_ids = data.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            logger.error(f"ClinVar search error for {gene_name}: {e}")
            return []

    if not variant_ids:
        return []

    # Fetch summaries
    results = await _fetch_clinvar_summaries(variant_ids)
    await cache_set(cache_key, results, ttl=3600 * 12)  # 12h
    return results


async def _fetch_clinvar_summaries(variant_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch ClinVar variant summaries for a list of variant IDs."""
    ids_str = ",".join(variant_ids[:10])
    params = {
        "db": "clinvar",
        "id": ids_str,
        "retmode": "json",
    }
    if settings.NCBI_API_KEY:
        params["api_key"] = settings.NCBI_API_KEY

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{settings.CLINVAR_BASE_URL}/esummary.fcgi", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"ClinVar summary fetch error: {e}")
            return []

    result_set = data.get("result", {})
    uids = result_set.get("uids", [])

    variants = []
    for uid in uids:
        entry = result_set.get(uid, {})
        if not entry:
            continue

        # Extract clinical significance
        germline = entry.get("germline_classification", {})
        clinical_sig = germline.get("description", entry.get("clinical_significance", {}).get("description", ""))

        # Disease name
        traits = entry.get("trait_set", [])
        disease_names = [t.get("trait_name", "") for t in traits if t.get("trait_name")]
        disease_name = "; ".join(disease_names[:3]) if disease_names else ""

        variants.append({
            "variant_id": uid,
            "clinical_significance": clinical_sig,
            "disease_name": disease_name,
            "review_status": entry.get("review_status", ""),
            "hgvs_expression": entry.get("title", ""),
            "last_evaluated": germline.get("last_evaluated", ""),
        })

    return variants
