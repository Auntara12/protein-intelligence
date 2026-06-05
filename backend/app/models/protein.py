from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db.database import Base


class Protein(Base):
    __tablename__ = "proteins"

    id = Column(Integer, primary_key=True, index=True)
    gene_name = Column(String(50), unique=True, index=True, nullable=False)
    uniprot_id = Column(String(20), index=True)
    protein_name = Column(String(255))
    organism = Column(String(100))
    sequence = Column(Text)
    sequence_length = Column(Integer)
    function_summary = Column(Text)
    domains = Column(JSON)           # list of domain dicts
    disease_annotations = Column(JSON)  # list of disease dicts
    go_terms = Column(JSON)
    subcellular_location = Column(String(255))
    mass_da = Column(Float)
    raw_uniprot = Column(JSON)       # full raw response for future use
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
