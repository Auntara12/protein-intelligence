"""
ESM2 + FAISS similarity service.

Architecture decision: embeddings stored as .npy files on disk,
FAISS index built in-memory and persisted as a binary file.
PostgreSQL stores metadata (gene, uniprot_id, faiss_index_id).
This is correct production architecture: FAISS is not a database,
it's an index. The DB holds metadata; FAISS holds the vectors.
"""

import os
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = Path("app/ml/faiss_store/index.faiss")
METADATA_PATH = Path("app/ml/faiss_store/metadata.json")
EMBEDDINGS_DIR = Path("app/ml/embeddings")

# Lazy-loaded globals
_model = None
_tokenizer = None
_faiss_index = None
_metadata: List[Dict] = []

# Track proteins currently being indexed in background to avoid duplicate work
_indexing_in_progress: set = set()


def is_indexed(gene_name: str) -> bool:
    """Return True if gene already has a vector in the FAISS index."""
    _, metadata = _load_faiss_index()
    return any(m["gene_name"] == gene_name.upper() for m in metadata)


def _ensure_dirs():
    FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)


def _load_esm2():
    """Lazy-load ESM2 model. Uses smallest ESM2 variant for speed."""
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer
    try:
        from transformers import EsmTokenizer, EsmModel
        import torch
        logger.info("Loading ESM2 model (facebook/esm2_t6_8M_UR50D)...")
        _tokenizer = EsmTokenizer.from_pretrained("facebook/esm2_t6_8M_UR50D")
        _model = EsmModel.from_pretrained("facebook/esm2_t6_8M_UR50D")
        _model.eval()
        logger.info("ESM2 model loaded.")
        return _model, _tokenizer
    except Exception as e:
        logger.error(f"ESM2 load failed: {e}")
        return None, None


def _load_faiss_index():
    """Load FAISS index and metadata from disk."""
    global _faiss_index, _metadata
    if _faiss_index is not None:
        return _faiss_index, _metadata
    try:
        import faiss
        if FAISS_INDEX_PATH.exists() and METADATA_PATH.exists():
            _faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
            with open(METADATA_PATH, "r") as f:
                _metadata = json.load(f)
            logger.info(f"FAISS index loaded: {_faiss_index.ntotal} vectors.")
        else:
            logger.info("No FAISS index found. Will create when embeddings are generated.")
    except Exception as e:
        logger.warning(f"FAISS load error: {e}")
    return _faiss_index, _metadata


def compute_embedding(sequence: str) -> Optional[np.ndarray]:
    """
    Compute ESM2 mean-pooled embedding for a protein sequence.
    Returns shape (320,) for esm2_t6_8M_UR50D.
    """
    import torch
    model, tokenizer = _load_esm2()
    if model is None:
        return None

    # Truncate very long sequences to avoid OOM (ESM2 max = 1022 tokens)
    sequence = sequence[:1022]

    try:
        inputs = tokenizer(sequence, return_tensors="pt", padding=True, truncation=True, max_length=1024)
        with torch.no_grad():
            outputs = model(**inputs)
        # Mean pool over sequence length dimension
        embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
        return embedding.astype(np.float32)
    except Exception as e:
        logger.error(f"Embedding computation error: {e}")
        return None


def add_to_index(gene_name: str, uniprot_id: str, embedding: np.ndarray) -> int:
    """
    Add an embedding vector to the FAISS index.
    Returns the FAISS index ID (position).
    Idempotent: if gene is already indexed, returns existing ID without re-adding.
    """
    global _faiss_index, _metadata

    import faiss
    _ensure_dirs()

    gene_upper = gene_name.upper()

    # If already indexed, return existing faiss_id (prevents orphaned vectors)
    existing = next((m for m in _metadata if m["gene_name"] == gene_upper), None)
    if existing is not None:
        logger.debug(f"{gene_upper} already in FAISS index at id={existing['faiss_id']}, skipping re-add.")
        return existing["faiss_id"]

    vec = embedding.reshape(1, -1).astype(np.float32)

    if _faiss_index is None:
        dim = vec.shape[1]
        # Inner product index after L2 normalization = cosine similarity
        _faiss_index = faiss.IndexFlatIP(dim)
        logger.info(f"Created new FAISS index with dim={dim}")

    # Normalize for cosine similarity
    faiss.normalize_L2(vec)
    _faiss_index.add(vec)

    index_id = _faiss_index.ntotal - 1

    _metadata.append({
        "faiss_id": index_id,
        "gene_name": gene_upper,
        "uniprot_id": uniprot_id,
    })

    # Persist
    faiss.write_index(_faiss_index, str(FAISS_INDEX_PATH))
    with open(METADATA_PATH, "w") as f:
        json.dump(_metadata, f, indent=2)

    # Save raw embedding
    np.save(str(EMBEDDINGS_DIR / f"{gene_name.upper()}.npy"), embedding)

    logger.info(f"Added {gene_name} to FAISS index at position {index_id}.")
    return index_id


def search_similar(query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
    """
    Search FAISS for top_k similar embeddings.
    Returns list of (faiss_id, similarity_score) tuples.
    """
    import faiss
    index, metadata = _load_faiss_index()
    if index is None or index.ntotal == 0:
        return []

    vec = query_embedding.reshape(1, -1).astype(np.float32)
    faiss.normalize_L2(vec)

    k = min(top_k + 1, index.ntotal)  # +1 to exclude self
    distances, indices = index.search(vec, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx >= 0:
            results.append((int(idx), float(dist)))

    return results


def get_metadata_by_faiss_id(faiss_id: int) -> Optional[Dict]:
    """Look up gene metadata by FAISS index position."""
    _, metadata = _load_faiss_index()
    for m in metadata:
        if m["faiss_id"] == faiss_id:
            return m
    return None


def get_index_stats() -> Dict[str, Any]:
    """Return FAISS index statistics."""
    index, metadata = _load_faiss_index()
    return {
        "total_indexed": index.ntotal if index else 0,
        "metadata_count": len(metadata),
        "index_path": str(FAISS_INDEX_PATH),
        "model": "facebook/esm2_t6_8M_UR50D",
        "embedding_dim": 320,
    }


# Seed proteins for initial index population
SEED_PROTEINS = [
    "TP53", "BRCA1", "BRCA2", "EGFR", "KRAS", "PTEN", "MYC",
    "AKT1", "BRAF", "PCDH15", "CDH23", "TP63", "TP73", "ATM",
    "CDKN2A", "RB1", "VHL", "MLH1", "MSH2", "ERBB2",
]
