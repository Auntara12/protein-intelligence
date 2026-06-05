"""batch.py"""
import time
import io
import csv
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.database import get_db
from app.schemas.schemas import BatchResponse, BatchMutationResult, BatchMutationInput
from app.services.uniprot_service import parse_mutation_string, analyze_mutation_properties, fetch_protein_from_uniprot
from app.services.clinvar_service import fetch_clinvar_variants

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 50


@router.post("/batch-analyze", response_model=BatchResponse)
async def batch_analyze(
    file: UploadFile = File(..., description="CSV with columns: gene, mutation"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a batch of mutations from a CSV file.
    Expected CSV format:
        gene,mutation
        TP53,R175H
        BRCA1,M1775R
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV.")

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    rows = list(reader)
    if len(rows) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum of {MAX_BATCH_SIZE} rows.",
        )

    required_cols = {"gene", "mutation"}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have columns: gene, mutation. Found: {reader.fieldnames}",
        )

    start_time = time.time()
    results: List[BatchMutationResult] = []
    successful = 0
    failed = 0

    for row in rows:
        gene = (row.get("gene") or "").strip().upper()
        mutation = (row.get("mutation") or "").strip().upper()

        if not gene or not mutation:
            results.append(BatchMutationResult(
                gene=gene, mutation=mutation, status="error",
                error="Missing gene or mutation value."
            ))
            failed += 1
            continue

        try:
            parse_result = parse_mutation_string(gene, mutation)
            if not parse_result["valid"]:
                raise ValueError(parse_result["error"])

            protein_data = await fetch_protein_from_uniprot(gene)
            domains = protein_data.get("domains", []) if protein_data else []
            prop_analysis = analyze_mutation_properties(
                parse_result["original_aa"],
                parse_result["mutated_aa"],
                domains,
                parse_result["position"],
            )
            clinvar_data = await fetch_clinvar_variants(gene, mutation)
            is_pathogenic = any(
                "pathogenic" in (v.get("clinical_significance") or "").lower()
                for v in clinvar_data
            )

            from app.schemas.schemas import MutationAnalysis, MutationParseResult
            analysis = MutationAnalysis(
                gene_name=gene,
                mutation_str=mutation,
                parse=MutationParseResult(**parse_result),
                charge_change=prop_analysis.get("charge_change"),
                polarity_change=prop_analysis.get("polarity_change"),
                size_change=prop_analysis.get("size_change"),
                hydrophobicity_change=prop_analysis.get("hydrophobicity_change"),
                domain=prop_analysis.get("domain"),
                structural_location=None,
                predicted_effect=prop_analysis.get("predicted_effect"),
                conservation_score=None,
                is_known_pathogenic=is_pathogenic,
                clinvar_data=clinvar_data,
            )
            results.append(BatchMutationResult(gene=gene, mutation=mutation, status="success", analysis=analysis))
            successful += 1

        except Exception as e:
            logger.error(f"Batch error for {gene} {mutation}: {e}")
            results.append(BatchMutationResult(
                gene=gene, mutation=mutation, status="error", error=str(e)
            ))
            failed += 1

    elapsed_ms = (time.time() - start_time) * 1000
    return BatchResponse(
        total=len(rows),
        successful=successful,
        failed=failed,
        results=results,
        processing_time_ms=round(elapsed_ms, 2),
    )
