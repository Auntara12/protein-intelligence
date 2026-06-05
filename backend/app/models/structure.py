from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db.database import Base


class Structure(Base):
    __tablename__ = "structures"

    id = Column(Integer, primary_key=True, index=True)
    gene_name = Column(String(50), unique=True, index=True, nullable=False)
    uniprot_id = Column(String(20))
    alphafold_url = Column(Text)        # CIF/PDB file URL from AlphaFold DB
    alphafold_pdb_url = Column(Text)    # PDB format URL
    pdb_id = Column(String(10))         # best matching PDB entry
    pdb_url = Column(Text)
    confidence_score = Column(Float)    # mean pLDDT score
    resolution_angstrom = Column(Float) # PDB resolution if available
    method = Column(String(50))         # X-ray, cryo-EM, AlphaFold, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    gene_name = Column(String(50), unique=True, index=True, nullable=False)
    uniprot_id = Column(String(20))
    model_name = Column(String(100), default="facebook/esm2_t6_8M_UR50D")
    embedding_dim = Column(Integer)
    embedding_path = Column(Text)       # path to .npy file
    faiss_index_id = Column(Integer)    # position in FAISS index
    sequence_length = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClinVar(Base):
    __tablename__ = "clinvar"

    id = Column(Integer, primary_key=True, index=True)
    gene_name = Column(String(50), index=True, nullable=False)
    mutation_str = Column(String(50), index=True)
    hgvs_expression = Column(String(255))
    clinical_significance = Column(String(100))  # Pathogenic, Benign, VUS, etc.
    disease_name = Column(Text)
    variant_id = Column(String(50))     # ClinVar variation ID
    review_status = Column(String(100))
    condition_mim = Column(String(50))  # OMIM ID if available
    last_evaluated = Column(String(50))
    raw_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
