from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.db.database import get_db
from app.models.protein import Protein
from app.models.structure import Embedding
from app.schemas.schemas import SimilarityResponse, SimilarProtein
from app.ml.esm2_service import (
    compute_embedding,
    add_to_index,
    search_similar,
    get_metadata_by_faiss_id,
    get_index_stats,
)
from app.services.uniprot_service import fetch_protein_from_uniprot

router = APIRouter()
logger = logging.getLogger(__name__)


async def _ensure_embedding(gene_name: str, db: AsyncSession) -> bool:
    """Ensure a gene has an embedding in the FAISS index. Returns True if successful."""
    # Get sequence
    prot_result = await db.execute(select(Protein).where(Protein.gene_name == gene_name))
    db_protein = prot_result.scalar_one_or_none()

    sequence = None
    uniprot_id = None

    if db_protein and db_protein.sequence:
        sequence = db_protein.sequence
        uniprot_id = db_protein.uniprot_id
    else:
        data = await fetch_protein_from_uniprot(gene_name)
        if data:
            sequence = data.get("sequence")
            uniprot_id = data.get("uniprot_id")

    if not sequence:
        return False

    embedding = compute_embedding(sequence)
    if embedding is None:
        return False

    faiss_id = add_to_index(gene_name, uniprot_id or "", embedding)

    # Store in DB
    emb_result = await db.execute(select(Embedding).where(Embedding.gene_name == gene_name))
    db_emb = emb_result.scalar_one_or_none()
    if not db_emb:
        db_emb = Embedding(
            gene_name=gene_name,
            uniprot_id=uniprot_id,
            model_name="facebook/esm2_t6_8M_UR50D",
            embedding_dim=embedding.shape[0],
            embedding_path=f"app/ml/embeddings/{gene_name}.npy",
            faiss_index_id=faiss_id,
            sequence_length=len(sequence),
        )
        db.add(db_emb)
        await db.flush()

    return True


@router.get("/similar/{gene_name}", response_model=SimilarityResponse)
async def get_similar_proteins(
    gene_name: str,
    top_k: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Find functionally similar proteins using ESM2 embeddings + FAISS cosine similarity.
    Automatically generates and indexes embeddings if not already present.
    """
    gene_upper = gene_name.upper().strip()
    stats = get_index_stats()

    # Ensure query gene is indexed
    emb_ok = await _ensure_embedding(gene_upper, db)
    if not emb_ok:
        raise HTTPException(
            status_code=503,
            detail="ESM2 model unavailable or sequence not found. Cannot compute similarity.",
        )

    # Load query embedding
    import numpy as np
    from pathlib import Path
    emb_path = Path(f"app/ml/embeddings/{gene_upper}.npy")
    if not emb_path.exists():
        raise HTTPException(status_code=500, detail="Embedding file not found after indexing.")

    query_embedding = np.load(str(emb_path))
    raw_results = search_similar(query_embedding, top_k=top_k + 1)

    # Build response, excluding self
    similar = []
    for faiss_id, score in raw_results:
        meta = get_metadata_by_faiss_id(faiss_id)
        if not meta or meta["gene_name"] == gene_upper:
            continue

        # Get protein name from DB
        prot_result = await db.execute(
            select(Protein).where(Protein.gene_name == meta["gene_name"])
        )
        db_prot = prot_result.scalar_one_or_none()

        similar.append(SimilarProtein(
            gene_name=meta["gene_name"],
            uniprot_id=meta.get("uniprot_id"),
            protein_name=db_prot.protein_name if db_prot else None,
            distance=1.0 - float(score),
            similarity_score=float(score),
            organism=db_prot.organism if db_prot else None,
        ))

        if len(similar) >= top_k:
            break

    updated_stats = get_index_stats()
    return SimilarityResponse(
        query_gene=gene_upper,
        results=similar,
        model_used="facebook/esm2_t6_8M_UR50D",
        total_indexed=updated_stats["total_indexed"],
    )


@router.post("/index/{gene_name}")
async def index_gene(gene_name: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger embedding generation and indexing for a gene."""
    gene_upper = gene_name.upper().strip()
    success = await _ensure_embedding(gene_upper, db)
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not index {gene_upper}.")
    stats = get_index_stats()
    return {"gene_name": gene_upper, "indexed": True, "total_in_index": stats["total_indexed"]}
