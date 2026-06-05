from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from app.db.database import get_db
from app.models.protein import Protein
from app.models.mutation import Mutation
from app.schemas.schemas import MutationAnalysis, MutationParseResult
from app.services.uniprot_service import (
    parse_mutation_string,
    analyze_mutation_properties,
    fetch_protein_from_uniprot,
)
from app.services.clinvar_service import fetch_clinvar_variants

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/mutation/{gene_name}/{mutation_str}", response_model=MutationAnalysis)
async def analyze_mutation(
    gene_name: str,
    mutation_str: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Full mutation analysis pipeline:
    1. Parse mutation string (R175H format)
    2. Validate against protein sequence
    3. Compute biochemical property changes
    4. Identify domain context
    5. Fetch ClinVar clinical significance
    """
    gene_upper = gene_name.upper().strip()
    mutation_upper = mutation_str.upper().strip()

    # Parse mutation
    parse_result = parse_mutation_string(gene_upper, mutation_upper)
    parse_schema = MutationParseResult(**parse_result)

    if not parse_result["valid"]:
        raise HTTPException(status_code=422, detail=parse_result["error"])

    # Check DB cache
    result = await db.execute(
        select(Mutation).where(
            and_(
                Mutation.gene_name == gene_upper,
                Mutation.mutation_str == mutation_upper,
            )
        )
    )
    db_mutation = result.scalar_one_or_none()

    # Get protein data (for domain context)
    protein_result = await db.execute(select(Protein).where(Protein.gene_name == gene_upper))
    db_protein = protein_result.scalar_one_or_none()

    domains = []
    if db_protein:
        domains = db_protein.domains or []
    else:
        protein_data = await fetch_protein_from_uniprot(gene_upper)
        if protein_data:
            domains = protein_data.get("domains", [])

    # Run property analysis
    prop_analysis = analyze_mutation_properties(
        orig_aa=parse_result["original_aa"],
        mut_aa=parse_result["mutated_aa"],
        domains=domains,
        position=parse_result["position"],
    )

    # Fetch ClinVar
    clinvar_data = await fetch_clinvar_variants(gene_upper, mutation_upper)
    is_pathogenic = any(
        "pathogenic" in (v.get("clinical_significance") or "").lower()
        for v in clinvar_data
    )

    # Cache in DB — use INSERT ON CONFLICT DO NOTHING to handle race conditions
    if not db_mutation:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(Mutation).values(
            gene_name=gene_upper,
            mutation_str=mutation_upper,
            original_aa=parse_result["original_aa"],
            position=parse_result["position"],
            mutated_aa=parse_result["mutated_aa"],
            domain=prop_analysis.get("domain"),
            charge_change=prop_analysis.get("charge_change"),
            polarity_change=prop_analysis.get("polarity_change"),
            size_change=prop_analysis.get("size_change"),
            hydrophobicity_change=prop_analysis.get("hydrophobicity_change"),
            predicted_effect=prop_analysis.get("predicted_effect"),
            is_known_pathogenic=is_pathogenic,
            analysis_details=prop_analysis.get("analysis_details"),
        ).on_conflict_do_nothing(constraint="uq_mutations_gene_mutation")
        await db.execute(stmt)
        await db.flush()

    return MutationAnalysis(
        gene_name=gene_upper,
        mutation_str=mutation_upper,
        parse=parse_schema,
        charge_change=prop_analysis.get("charge_change"),
        polarity_change=prop_analysis.get("polarity_change"),
        size_change=prop_analysis.get("size_change"),
        hydrophobicity_change=prop_analysis.get("hydrophobicity_change"),
        domain=prop_analysis.get("domain"),
        structural_location=db_mutation.structural_location if db_mutation else None,
        predicted_effect=prop_analysis.get("predicted_effect"),
        conservation_score=db_mutation.conservation_score if db_mutation else None,
        is_known_pathogenic=is_pathogenic,
        clinvar_data=clinvar_data,
        cached=False,
    )
