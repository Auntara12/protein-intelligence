"""report.py — JSON report, PDF export, and protein comparison"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from app.db.database import get_db
from app.schemas.schemas import ReportResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def _build_report(gene_upper: str, mutation_str, db: AsyncSession) -> ReportResponse:
    """Shared logic for JSON and PDF report generation."""
    from app.api.routes.protein import get_protein
    from app.api.routes.structure import get_structure

    try:
        protein_data = await get_protein(gene_upper, organism="human", refresh=False, db=db)
    except HTTPException:
        protein_data = None

    mutation_data = None
    if mutation_str:
        try:
            from app.api.routes.mutation import analyze_mutation
            mutation_data = await analyze_mutation(gene_upper, mutation_str.upper(), db=db)
        except HTTPException:
            mutation_data = None

    try:
        mutation_pos = mutation_data.parse.position if mutation_data else None
        structure_data = await get_structure(gene_upper, mutation_position=mutation_pos, db=db)
    except HTTPException:
        structure_data = None

    similar = []
    try:
        from app.api.routes.similarity import get_similar_proteins
        sim_result = await get_similar_proteins(gene_upper, top_k=5, db=db)
        similar = sim_result.results
    except Exception:
        pass

    clinvar = mutation_data.clinvar_data if mutation_data else []

    return ReportResponse(
        gene_name=gene_upper,
        mutation_str=mutation_str,
        protein=protein_data,
        mutation=mutation_data,
        structure=structure_data,
        similar_proteins=similar,
        clinvar=clinvar,
        generated_at=datetime.utcnow(),
        format="json",
    )


@router.get("/report/{gene_name}", response_model=ReportResponse)
async def get_report(
    gene_name: str,
    mutation_str: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Assemble a full research report for a gene (and optionally a mutation).
    Aggregates: protein metadata, mutation analysis, structure, similar proteins, ClinVar.
    """
    gene_upper = gene_name.upper().strip()
    return await _build_report(gene_upper, mutation_str, db)


@router.get("/report/{gene_name}/pdf")
async def download_report_pdf(
    gene_name: str,
    mutation_str: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a PDF research report for a gene (and optionally a mutation).
    Returns a downloadable PDF file.
    """
    gene_upper = gene_name.upper().strip()
    report = await _build_report(gene_upper, mutation_str, db)

    from app.services.pdf_service import generate_report_pdf
    import asyncio

    # PDF generation is CPU-bound — run in thread pool
    report_dict = report.model_dump(mode="json")
    try:
        pdf_bytes = await asyncio.to_thread(generate_report_pdf, report_dict)
    except Exception as e:
        logger.error(f"PDF generation failed for {gene_upper}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename = f"{gene_upper}"
    if mutation_str:
        filename += f"_{mutation_str.upper()}"
    filename += "_report.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.get("/compare/{gene1}/{gene2}")
async def compare_proteins(
    gene1: str,
    gene2: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Side-by-side comparison of two proteins.
    Returns protein metadata, Smith-Waterman alignment, shared/divergent domains,
    disease association overlap, and ESM2 similarity (if both are indexed).

    Combines the /align and /protein endpoints into a single comparison payload
    designed for the frontend comparison view.
    """
    import asyncio
    from app.api.routes.protein import get_protein
    from app.api.routes.alignment import align_sequences

    g1 = gene1.upper().strip()
    g2 = gene2.upper().strip()

    if g1 == g2:
        raise HTTPException(status_code=400, detail="Cannot compare a protein with itself.")

    # Fetch sequentially — asyncio.gather with a shared db session causes
    # concurrent session access errors in SQLAlchemy async.
    p1 = await _safe_get_protein(g1, db)
    p2 = await _safe_get_protein(g2, db)

    if not p1:
        raise HTTPException(status_code=404, detail=f"Protein '{g1}' not found.")
    if not p2:
        raise HTTPException(status_code=404, detail=f"Protein '{g2}' not found.")

    # Run alignment
    alignment = None
    try:
        alignment_result = await align_sequences(g1, g2, max_length=500, db=db)
        alignment = alignment_result.model_dump()
    except Exception as e:
        logger.warning(f"Alignment failed for {g1}/{g2}: {e}")

    # ESM2 similarity (if both indexed)
    esm2_similarity = None
    try:
        from app.api.routes.similarity import get_similar_proteins
        sim_result = await get_similar_proteins(g1, top_k=20, db=db)
        for sp in sim_result.results:
            if sp.gene_name == g2:
                esm2_similarity = sp.similarity_score
                break
    except Exception:
        pass

    # Find shared and divergent domains
    domains1 = {d.get("name", "") for d in (p1.get("domains") or []) if d.get("name")}
    domains2 = {d.get("name", "") for d in (p2.get("domains") or []) if d.get("name")}
    shared_domains = sorted(domains1 & domains2)
    unique_to_1 = sorted(domains1 - domains2)
    unique_to_2 = sorted(domains2 - domains1)

    # Find shared disease associations
    diseases1 = {d.get("name", "") for d in (p1.get("disease_annotations") or []) if d.get("name")}
    diseases2 = {d.get("name", "") for d in (p2.get("disease_annotations") or []) if d.get("name")}
    shared_diseases = sorted(diseases1 & diseases2)

    return {
        "gene1": g1,
        "gene2": g2,
        "protein1": p1,
        "protein2": p2,
        "alignment": alignment,
        "esm2_similarity": esm2_similarity,
        "domain_comparison": {
            "shared": shared_domains,
            "unique_to_gene1": unique_to_1,
            "unique_to_gene2": unique_to_2,
        },
        "shared_diseases": shared_diseases,
        "summary": _generate_comparison_summary(g1, g2, alignment, esm2_similarity, shared_domains),
    }


async def _safe_get_protein(gene: str, db: AsyncSession):
    """Fetch protein as dict, returning None on failure."""
    try:
        from app.api.routes.protein import get_protein
        result = await get_protein(gene, organism="human", refresh=False, db=db)
        return result.model_dump()
    except Exception:
        return None


def _generate_comparison_summary(
    g1: str, g2: str, alignment: dict, esm2_sim: float, shared_domains: list
) -> str:
    """Generate a one-paragraph natural language comparison summary."""
    parts = []

    if alignment:
        ident = alignment.get("identity_pct", 0)
        score = alignment.get("score", 0)
        if ident >= 50:
            parts.append(
                f"{g1} and {g2} share high sequence identity ({ident:.1f}%), "
                "suggesting a shared evolutionary origin and likely conserved function."
            )
        elif ident >= 25:
            parts.append(
                f"{g1} and {g2} have moderate sequence identity ({ident:.1f}%), "
                "indicating possible homology with functional divergence."
            )
        else:
            parts.append(
                f"{g1} and {g2} have low sequence identity ({ident:.1f}%), "
                "suggesting convergent evolution or functional independence."
            )

    if esm2_sim is not None:
        sim_pct = esm2_sim * 100
        if esm2_sim >= 0.8:
            parts.append(
                f"ESM2 embedding similarity is high ({sim_pct:.1f}%), "
                "indicating similar structural and functional representations."
            )
        elif esm2_sim >= 0.5:
            parts.append(f"ESM2 similarity is moderate ({sim_pct:.1f}%).")
        else:
            parts.append(
                f"ESM2 similarity is low ({sim_pct:.1f}%), "
                "suggesting structurally or functionally distinct proteins."
            )

    if shared_domains:
        parts.append(
            f"Both proteins share {len(shared_domains)} annotated domain(s): "
            f"{', '.join(shared_domains[:3])}."
        )

    return " ".join(parts) if parts else f"Comparison between {g1} and {g2}."
