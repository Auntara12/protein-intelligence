"""
Smith-Waterman sequence alignment endpoint.

Why this endpoint exists separately from /similar:
  /similar/{gene} uses ESM2 embeddings — it captures structural and
  functional similarity even between proteins with low sequence identity
  (e.g., convergently evolved proteins).

  /align/{gene1}/{gene2} uses Smith-Waterman — it finds the best
  locally aligned subsequence. High alignment score with low ESM2
  similarity suggests functional divergence despite sequence conservation.
  High ESM2 similarity with low alignment score suggests structural
  convergence without sequence homology.

  The comparison between the two is biologically meaningful and is a
  strong interview talking point.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import asyncio
import logging

from app.db.database import get_db
from app.models.protein import Protein
from app.services.uniprot_service import fetch_protein_from_uniprot
from app.ml.alignment import smith_waterman, AlignmentResult
from app.core.cache import cache_get, cache_set, make_cache_key

router = APIRouter()
logger = logging.getLogger(__name__)


class AlignmentResponse(BaseModel):
    gene1: str
    gene2: str
    score: int
    identity_pct: float
    similarity_pct: float
    alignment_length: int
    gaps: int
    query_aligned: str
    target_aligned: str
    match_line: str
    query_start: int
    query_end: int
    target_start: int
    target_end: int
    interpretation: str
    truncated: bool
    cached: bool


@router.get("/align/{gene1}/{gene2}", response_model=AlignmentResponse)
async def align_sequences(
    gene1: str,
    gene2: str,
    max_length: int = Query(default=500, ge=50, le=2000, description="Max residues per sequence (performance guard)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Smith-Waterman local sequence alignment between two proteins.

    Uses BLOSUM62 substitution matrix with affine gap penalties
    (gap open: -11, gap extend: -1) — the same parameters used by BLAST.

    Returns percent identity, similarity, aligned sequences, and an
    interpretation of the biological significance.
    """
    g1 = gene1.upper().strip()
    g2 = gene2.upper().strip()

    if g1 == g2:
        raise HTTPException(status_code=400, detail="Cannot align a protein with itself.")

    # Cache check
    cache_key = make_cache_key("align", g1, g2, str(max_length))
    cached = await cache_get(cache_key)
    if cached:
        return AlignmentResponse(**{**cached, "cached": True})

    # Fetch sequences in parallel
    seq1, seq2 = await asyncio.gather(
        _get_sequence(g1, db),
        _get_sequence(g2, db),
    )

    if not seq1:
        raise HTTPException(status_code=404, detail=f"Sequence not found for {g1}.")
    if not seq2:
        raise HTTPException(status_code=404, detail=f"Sequence not found for {g2}.")

    truncated = len(seq1) > max_length or len(seq2) > max_length

    # Run alignment in a thread (CPU-bound O(mn) DP)
    result: AlignmentResult = await asyncio.to_thread(
        smith_waterman, seq1, seq2, max_length
    )

    interpretation = _interpret_alignment(result, g1, g2)

    response_data = {
        "gene1": g1,
        "gene2": g2,
        "score": result.score,
        "identity_pct": result.identity_pct,
        "similarity_pct": result.similarity_pct,
        "alignment_length": result.alignment_length,
        "gaps": result.gaps,
        "query_aligned": result.query_aligned[:200],   # truncate for JSON
        "target_aligned": result.target_aligned[:200],
        "match_line": result.match_line[:200],
        "query_start": result.query_start,
        "query_end": result.query_end,
        "target_start": result.target_start,
        "target_end": result.target_end,
        "interpretation": interpretation,
        "truncated": truncated,
        "cached": False,
    }

    await cache_set(cache_key, response_data, ttl=3600 * 6)
    return AlignmentResponse(**response_data)


async def _get_sequence(gene: str, db: AsyncSession) -> Optional[str]:
    """Get sequence from DB or UniProt."""
    result = await db.execute(select(Protein).where(Protein.gene_name == gene))
    db_protein = result.scalar_one_or_none()
    if db_protein and db_protein.sequence:
        return db_protein.sequence

    data = await fetch_protein_from_uniprot(gene)
    return data.get("sequence") if data else None


def _interpret_alignment(result: AlignmentResult, g1: str, g2: str) -> str:
    """
    Generate a human-readable interpretation of alignment results.
    Thresholds follow standard bioinformatics conventions.
    """
    ident = result.identity_pct
    sim = result.similarity_pct

    if ident >= 90:
        return (
            f"{g1} and {g2} are nearly identical ({ident:.1f}% identity). "
            "Likely orthologues or paralogues with very recent divergence."
        )
    elif ident >= 50:
        return (
            f"High sequence identity ({ident:.1f}%) between {g1} and {g2}. "
            "Strong evidence of shared evolutionary origin and likely conserved function. "
            f"Similarity including conservative substitutions: {sim:.1f}%."
        )
    elif ident >= 30:
        return (
            f"Moderate sequence identity ({ident:.1f}%) between {g1} and {g2}. "
            "Proteins are likely homologous with conserved core structure "
            "but possible functional divergence. "
            f"Similarity: {sim:.1f}%."
        )
    elif ident >= 20:
        return (
            f"Low sequence identity ({ident:.1f}%) — in the 'twilight zone' of homology detection. "
            "Structural similarity may exist despite limited sequence conservation. "
            "Compare with ESM2 embedding similarity for a fuller picture."
        )
    else:
        return (
            f"Very low sequence identity ({ident:.1f}%) between {g1} and {g2}. "
            "Proteins are likely not homologous by sequence alone. "
            "Any functional similarity is likely due to convergent evolution. "
            "ESM2 embedding similarity may still detect structural resemblance."
        )
