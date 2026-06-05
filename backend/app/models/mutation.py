from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from app.db.database import Base


class Mutation(Base):
    __tablename__ = "mutations"

    id = Column(Integer, primary_key=True, index=True)
    gene_name = Column(String(50), index=True, nullable=False)
    mutation_str = Column(String(50), index=True, nullable=False)  # e.g. R175H
    original_aa = Column(String(5))
    position = Column(Integer)
    mutated_aa = Column(String(5))
    domain = Column(String(255))
    charge_change = Column(String(200))
    polarity_change = Column(String(200))
    size_change = Column(String(200))
    hydrophobicity_change = Column(String(200))
    predicted_effect = Column(Text)
    conservation_score = Column(Float)
    is_known_pathogenic = Column(Boolean, default=False)
    structural_location = Column(String(255))
    analysis_details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
