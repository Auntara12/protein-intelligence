from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Protein ──────────────────────────────────────────────────────────────────

class DomainInfo(BaseModel):
    name: str
    start: Optional[int] = None
    end: Optional[int] = None
    description: Optional[str] = None


class DiseaseAnnotation(BaseModel):
    name: str
    description: Optional[str] = None
    mim_id: Optional[str] = None


class ProteinResponse(BaseModel):
    gene_name: str
    uniprot_id: Optional[str]
    protein_name: Optional[str]
    organism: Optional[str]
    sequence: Optional[str]
    sequence_length: Optional[int]
    function_summary: Optional[str]
    domains: Optional[List[Dict[str, Any]]] = []
    disease_annotations: Optional[List[Dict[str, Any]]] = []
    go_terms: Optional[List[Dict[str, Any]]] = []
    subcellular_location: Optional[str]
    mass_da: Optional[float]
    cached: bool = False

    class Config:
        from_attributes = True


# ── Mutation ──────────────────────────────────────────────────────────────────

class MutationParseResult(BaseModel):
    raw: str
    gene: str
    original_aa: str
    original_aa_full: str
    position: int
    mutated_aa: str
    mutated_aa_full: str
    valid: bool
    error: Optional[str] = None


class MutationAnalysis(BaseModel):
    gene_name: str
    mutation_str: str
    parse: MutationParseResult
    charge_change: Optional[str]
    polarity_change: Optional[str]
    size_change: Optional[str]
    hydrophobicity_change: Optional[str]
    domain: Optional[str]
    structural_location: Optional[str]
    predicted_effect: Optional[str]
    conservation_score: Optional[float]
    is_known_pathogenic: bool = False
    clinvar_data: Optional[List[Dict[str, Any]]] = []
    cached: bool = False


# ── Structure ─────────────────────────────────────────────────────────────────

class StructureResponse(BaseModel):
    gene_name: str
    uniprot_id: Optional[str]
    alphafold_url: Optional[str]
    alphafold_pdb_url: Optional[str]
    pdb_id: Optional[str]
    pdb_url: Optional[str]
    confidence_score: Optional[float]
    resolution_angstrom: Optional[float]
    method: Optional[str]
    viewer_config: Optional[Dict[str, Any]] = {}
    cached: bool = False

    class Config:
        from_attributes = True


# ── Similarity ────────────────────────────────────────────────────────────────

class SimilarProtein(BaseModel):
    gene_name: str
    uniprot_id: Optional[str]
    protein_name: Optional[str]
    distance: float
    similarity_score: float  # 0-1, higher = more similar
    organism: Optional[str]


class SimilarityResponse(BaseModel):
    query_gene: str
    results: List[SimilarProtein]
    model_used: str
    total_indexed: int


# ── ClinVar ───────────────────────────────────────────────────────────────────

class ClinVarEntry(BaseModel):
    variant_id: Optional[str]
    clinical_significance: Optional[str]
    disease_name: Optional[str]
    review_status: Optional[str]
    hgvs_expression: Optional[str]
    last_evaluated: Optional[str]


# ── Batch ─────────────────────────────────────────────────────────────────────

class BatchMutationInput(BaseModel):
    gene: str
    mutation: str


class BatchMutationResult(BaseModel):
    gene: str
    mutation: str
    status: str  # success / error
    analysis: Optional[MutationAnalysis] = None
    error: Optional[str] = None


class BatchResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[BatchMutationResult]
    processing_time_ms: float


# ── Report ────────────────────────────────────────────────────────────────────

class ReportResponse(BaseModel):
    gene_name: str
    mutation_str: Optional[str]
    protein: Optional[ProteinResponse]
    mutation: Optional[MutationAnalysis]
    structure: Optional[StructureResponse]
    similar_proteins: Optional[List[SimilarProtein]] = []
    clinvar: Optional[List[ClinVarEntry]] = []
    generated_at: datetime
    format: str = "json"


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    faiss_index: str
    version: str = "1.0.0"
