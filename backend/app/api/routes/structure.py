"""structure.py"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.db.database import get_db
from app.models.protein import Protein
from app.models.structure import Structure
from app.schemas.schemas import StructureResponse
from app.services.structure_service import (
    fetch_alphafold_structure,
    fetch_pdb_structure,
    build_3dmol_config,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/structure/{gene_name}", response_model=StructureResponse)
async def get_structure(
    gene_name: str,
    mutation_position: int = Query(default=None, description="Highlight this residue position"),
    db: AsyncSession = Depends(get_db),
):
    gene_upper = gene_name.upper().strip()

    # Check DB
    result = await db.execute(select(Structure).where(Structure.gene_name == gene_upper))
    db_struct = result.scalar_one_or_none()
    if db_struct:
        viewer_config = build_3dmol_config(
            db_struct.alphafold_pdb_url or db_struct.pdb_url or "",
            mutation_position=mutation_position,
        )
        return StructureResponse(
            gene_name=gene_upper,
            uniprot_id=db_struct.uniprot_id,
            alphafold_url=db_struct.alphafold_url,
            alphafold_pdb_url=db_struct.alphafold_pdb_url,
            pdb_id=db_struct.pdb_id,
            pdb_url=db_struct.pdb_url,
            confidence_score=db_struct.confidence_score,
            resolution_angstrom=db_struct.resolution_angstrom,
            method=db_struct.method,
            viewer_config=viewer_config,
            cached=True,
        )

    # Get uniprot_id from protein table
    prot_result = await db.execute(select(Protein).where(Protein.gene_name == gene_upper))
    db_protein = prot_result.scalar_one_or_none()
    uniprot_id = db_protein.uniprot_id if db_protein else None

    # Fetch AlphaFold + PDB in parallel
    import asyncio

    async def _none():
        return None

    af_coro = fetch_alphafold_structure(uniprot_id) if uniprot_id else _none()
    pdb_coro = fetch_pdb_structure(gene_upper, uniprot_id)
    af_data, pdb_data = await asyncio.gather(af_coro, pdb_coro)

    if not af_data and not pdb_data:
        raise HTTPException(status_code=404, detail=f"No structure found for {gene_upper}")

    db_struct = Structure(
        gene_name=gene_upper,
        uniprot_id=uniprot_id,
        alphafold_url=af_data.get("alphafold_url") if af_data else None,
        alphafold_pdb_url=af_data.get("alphafold_pdb_url") if af_data else None,
        confidence_score=af_data.get("confidence_score") if af_data else None,
        pdb_id=pdb_data.get("pdb_id") if pdb_data else None,
        pdb_url=pdb_data.get("pdb_url") if pdb_data else None,
        resolution_angstrom=pdb_data.get("resolution_angstrom") if pdb_data else None,
        method=pdb_data.get("method") if pdb_data else ("AlphaFold" if af_data else None),
    )
    db.add(db_struct)
    await db.flush()

    struct_url = (af_data or {}).get("alphafold_pdb_url") or (pdb_data or {}).get("pdb_url") or ""
    viewer_config = build_3dmol_config(struct_url, mutation_position=mutation_position)

    return StructureResponse(
        gene_name=gene_upper,
        uniprot_id=uniprot_id,
        alphafold_url=(af_data or {}).get("alphafold_url"),
        alphafold_pdb_url=(af_data or {}).get("alphafold_pdb_url"),
        pdb_id=(pdb_data or {}).get("pdb_id"),
        pdb_url=(pdb_data or {}).get("pdb_url"),
        confidence_score=(af_data or {}).get("confidence_score"),
        resolution_angstrom=(pdb_data or {}).get("resolution_angstrom"),
        method=(pdb_data or {}).get("method") or ("AlphaFold" if af_data else None),
        viewer_config=viewer_config,
        cached=False,
    )
