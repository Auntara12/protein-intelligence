import httpx
import logging
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.cache import cache_get, cache_set, make_cache_key

logger = logging.getLogger(__name__)


async def fetch_alphafold_structure(uniprot_id: str) -> Optional[Dict[str, Any]]:
    """Fetch AlphaFold structure metadata and file URLs for a UniProt accession."""
    if not uniprot_id:
        return None

    cache_key = make_cache_key("alphafold", uniprot_id)
    cached = await cache_get(cache_key)
    if cached:
        return {**cached, "cached": True}

    url = f"{settings.ALPHAFOLD_BASE_URL}/prediction/{uniprot_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning(f"No AlphaFold entry for {uniprot_id}")
                return None
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"AlphaFold fetch error for {uniprot_id}: {e}")
            return None

    if not data:
        return None

    entry = data[0] if isinstance(data, list) else data

    result = {
        "uniprot_id": uniprot_id,
        "alphafold_url": entry.get("cifUrl"),
        "alphafold_pdb_url": entry.get("pdbUrl"),
        "confidence_score": entry.get("globalMetricValue") or entry.get("confidenceAvgLocalScore"),
        "model_created_date": entry.get("modelCreatedDate"),
        "latest_version": entry.get("latestVersion"),
        "cached": False,
    }

    await cache_set(cache_key, result, ttl=86400 * 7)  # 7 days
    return result


async def fetch_pdb_structure(gene_name: str, uniprot_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Search PDB for the best experimental structure for a gene/protein.
    Returns the top result with metadata.
    """
    cache_key = make_cache_key("pdb", gene_name)
    cached = await cache_get(cache_key)
    if cached:
        return {**cached, "cached": True}

    # Search PDB by gene name
    search_query = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": gene_name},
        },
        "return_type": "entry",
        "request_options": {
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "score", "direction": "desc"}],
            "results_verbosity": "minimal",
        },
        "paginate": {"start": 0, "rows": 5},
    }

    pdb_id = None
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                settings.PDB_SEARCH_URL,
                json=search_query,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 204:
                logger.info(f"No PDB results for {gene_name}")
            elif response.status_code == 200:
                data = response.json()
                results = data.get("result_set", [])
                if results:
                    pdb_id = results[0].get("identifier")
        except Exception as e:
            logger.warning(f"PDB search error for {gene_name}: {e}")

    if not pdb_id:
        return None

    # Fetch structure details
    details = await _fetch_pdb_entry_details(pdb_id)
    if details:
        result = {
            "pdb_id": pdb_id,
            "pdb_url": f"https://files.rcsb.org/download/{pdb_id}.pdb",
            "pdb_cif_url": f"https://files.rcsb.org/download/{pdb_id}.cif",
            "resolution_angstrom": details.get("resolution"),
            "method": details.get("method"),
            "deposition_date": details.get("deposition_date"),
            "cached": False,
        }
        await cache_set(cache_key, result, ttl=86400 * 7)
        return result

    return None


async def _fetch_pdb_entry_details(pdb_id: str) -> Optional[Dict[str, Any]]:
    """Fetch resolution and method for a PDB entry."""
    url = f"{settings.PDB_BASE_URL}/entry/{pdb_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            refine = data.get("refine", [{}])
            method_info = data.get("exptl", [{}])
            return {
                "resolution": refine[0].get("ls_d_res_high") if refine else None,
                "method": method_info[0].get("method") if method_info else "Unknown",
                "deposition_date": data.get("rcsb_accession_info", {}).get("deposit_date"),
            }
        except Exception as e:
            logger.warning(f"PDB detail fetch error for {pdb_id}: {e}")
            return None


def build_3dmol_config(
    structure_url: str,
    mutation_position: Optional[int] = None,
    highlight_domains: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Build configuration object for 3Dmol.js viewer in the frontend.
    Returns a dict that the React component can consume directly.
    """
    config = {
        "url": structure_url,
        "format": "pdb" if structure_url.endswith(".pdb") else "cif",
        "defaultStyle": {
            "cartoon": {
                "colorscheme": "ssJmol",  # color by secondary structure
                "opacity": 1.0,
            }
        },
        "backgroundColor": "0x1a1a2e",
        "mutations": [],
        "domains": [],
    }

    if mutation_position:
        config["mutations"].append({
            "resi": mutation_position,
            "style": {
                "stick": {"colorscheme": "redCarbon", "radius": 0.3},
                "sphere": {"color": "red", "radius": 0.8},
            },
            "label": f"Mutation site: {mutation_position}",
        })

    if highlight_domains:
        colors = ["#4ecdc4", "#45b7d1", "#96ceb4", "#ffeaa7", "#dda0dd"]
        for i, domain in enumerate(highlight_domains[:5]):
            start = domain.get("start")
            end = domain.get("end")
            if start and end:
                config["domains"].append({
                    "resi": f"{start}-{end}",
                    "color": colors[i % len(colors)],
                    "label": domain.get("name", f"Domain {i+1}"),
                })

    return config
