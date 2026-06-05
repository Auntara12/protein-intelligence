from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import logging

from app.db.database import get_db
from app.models.protein import Protein
from app.schemas.schemas import ProteinResponse
from app.services.uniprot_service import fetch_protein_from_uniprot

router = APIRouter()
logger = logging.getLogger(__name__)


async def _bg_index_protein(gene_name: str, sequence: str, uniprot_id: str) -> None:
    """Background task: compute ESM2 embedding and add to FAISS. No DB session needed."""
    from app.ml.esm2_service import compute_embedding, add_to_index, _indexing_in_progress, is_indexed
    if gene_name in _indexing_in_progress or is_indexed(gene_name):
        return
    _indexing_in_progress.add(gene_name)
    try:
        embedding = await asyncio.to_thread(compute_embedding, sequence)
        if embedding is not None:
            add_to_index(gene_name, uniprot_id, embedding)
            logger.info(f"Background indexing complete for {gene_name}.")
    except Exception as e:
        logger.warning(f"Background indexing failed for {gene_name}: {e}")
    finally:
        _indexing_in_progress.discard(gene_name)


@router.get("/protein/{gene_name}", response_model=ProteinResponse)
async def get_protein(
    gene_name: str,
    organism: str = Query(default="human", description="Organism (default: human)"),
    refresh: bool = Query(default=False, description="Force refresh from UniProt"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve full protein metadata for a gene symbol.

    - Checks PostgreSQL cache first
    - Falls back to UniProt REST API
    - Stores result in DB for future requests
    """
    gene_upper = gene_name.upper().strip()

    # Check DB first (unless refresh requested)
    if not refresh:
        result = await db.execute(select(Protein).where(Protein.gene_name == gene_upper))
        db_protein = result.scalar_one_or_none()
        if db_protein:
            logger.info(f"DB hit for gene: {gene_upper}")
            from app.ml.esm2_service import is_indexed
            if not is_indexed(gene_upper) and db_protein.sequence:
                asyncio.create_task(
                    _bg_index_protein(gene_upper, db_protein.sequence, db_protein.uniprot_id or "")
                )
            return ProteinResponse(
                gene_name=db_protein.gene_name,
                uniprot_id=db_protein.uniprot_id,
                protein_name=db_protein.protein_name,
                organism=db_protein.organism,
                sequence=db_protein.sequence,
                sequence_length=db_protein.sequence_length,
                function_summary=db_protein.function_summary,
                domains=db_protein.domains or [],
                disease_annotations=db_protein.disease_annotations or [],
                go_terms=db_protein.go_terms or [],
                subcellular_location=db_protein.subcellular_location,
                mass_da=db_protein.mass_da,
                cached=True,
            )

    # Fetch from UniProt
    data = await fetch_protein_from_uniprot(gene_upper, organism)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Protein '{gene_upper}' not found in UniProt. Check the gene symbol and try again.",
        )

    # Upsert into DB
    result = await db.execute(select(Protein).where(Protein.gene_name == gene_upper))
    existing = result.scalar_one_or_none()

    if existing:
        for field, value in data.items():
            if hasattr(existing, field) and field not in ("cached",):
                setattr(existing, field, value)
        db_protein = existing
    else:
        db_protein = Protein(**{k: v for k, v in data.items() if k not in ("cached",)})
        db.add(db_protein)

    await db.flush()

    from app.ml.esm2_service import is_indexed
    if not is_indexed(gene_upper) and data.get("sequence"):
        asyncio.create_task(
            _bg_index_protein(gene_upper, data["sequence"], data.get("uniprot_id", ""))
        )

    return ProteinResponse(**{**data, "cached": data.get("cached", False)})


@router.get("/protein/{gene_name}/sequence")
async def get_sequence(gene_name: str, db: AsyncSession = Depends(get_db)):
    """Return just the amino acid sequence for a gene. Useful for embedding generation."""
    gene_upper = gene_name.upper().strip()
    result = await db.execute(select(Protein).where(Protein.gene_name == gene_upper))
    db_protein = result.scalar_one_or_none()

    if db_protein and db_protein.sequence:
        return {"gene_name": gene_upper, "sequence": db_protein.sequence, "length": db_protein.sequence_length}

    data = await fetch_protein_from_uniprot(gene_upper)
    if not data or not data.get("sequence"):
        raise HTTPException(status_code=404, detail=f"Sequence not found for {gene_upper}")

    return {"gene_name": gene_upper, "sequence": data["sequence"], "length": data["sequence_length"]}
