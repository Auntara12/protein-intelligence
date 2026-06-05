"""Initial schema: proteins, mutations, structures, embeddings, clinvar

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── proteins ──────────────────────────────────────────────────────────────
    op.create_table(
        "proteins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gene_name", sa.String(50), nullable=False),
        sa.Column("uniprot_id", sa.String(20), nullable=True),
        sa.Column("protein_name", sa.String(255), nullable=True),
        sa.Column("organism", sa.String(100), nullable=True),
        sa.Column("sequence", sa.Text(), nullable=True),
        sa.Column("sequence_length", sa.Integer(), nullable=True),
        sa.Column("function_summary", sa.Text(), nullable=True),
        sa.Column("domains", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("disease_annotations", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("go_terms", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("subcellular_location", sa.String(255), nullable=True),
        sa.Column("mass_da", sa.Float(), nullable=True),
        sa.Column("raw_uniprot", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_proteins_gene_name", "proteins", ["gene_name"], unique=True)
    op.create_index("ix_proteins_uniprot_id", "proteins", ["uniprot_id"])

    # ── mutations ─────────────────────────────────────────────────────────────
    op.create_table(
        "mutations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gene_name", sa.String(50), nullable=False),
        sa.Column("mutation_str", sa.String(50), nullable=False),
        sa.Column("original_aa", sa.String(5), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("mutated_aa", sa.String(5), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("charge_change", sa.String(50), nullable=True),
        sa.Column("polarity_change", sa.String(50), nullable=True),
        sa.Column("size_change", sa.String(50), nullable=True),
        sa.Column("hydrophobicity_change", sa.String(50), nullable=True),
        sa.Column("predicted_effect", sa.Text(), nullable=True),
        sa.Column("conservation_score", sa.Float(), nullable=True),
        sa.Column("is_known_pathogenic", sa.Boolean(), nullable=True),
        sa.Column("structural_location", sa.String(255), nullable=True),
        sa.Column("analysis_details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mutations_gene_name", "mutations", ["gene_name"])
    op.create_index("ix_mutations_mutation_str", "mutations", ["mutation_str"])

    # ── structures ────────────────────────────────────────────────────────────
    op.create_table(
        "structures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gene_name", sa.String(50), nullable=False),
        sa.Column("uniprot_id", sa.String(20), nullable=True),
        sa.Column("alphafold_url", sa.Text(), nullable=True),
        sa.Column("alphafold_pdb_url", sa.Text(), nullable=True),
        sa.Column("pdb_id", sa.String(10), nullable=True),
        sa.Column("pdb_url", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("resolution_angstrom", sa.Float(), nullable=True),
        sa.Column("method", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_structures_gene_name", "structures", ["gene_name"], unique=True)

    # ── embeddings ────────────────────────────────────────────────────────────
    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gene_name", sa.String(50), nullable=False),
        sa.Column("uniprot_id", sa.String(20), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("embedding_path", sa.Text(), nullable=True),
        sa.Column("faiss_index_id", sa.Integer(), nullable=True),
        sa.Column("sequence_length", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_embeddings_gene_name", "embeddings", ["gene_name"], unique=True)

    # ── clinvar ───────────────────────────────────────────────────────────────
    op.create_table(
        "clinvar",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gene_name", sa.String(50), nullable=False),
        sa.Column("mutation_str", sa.String(50), nullable=True),
        sa.Column("hgvs_expression", sa.String(255), nullable=True),
        sa.Column("clinical_significance", sa.String(100), nullable=True),
        sa.Column("disease_name", sa.Text(), nullable=True),
        sa.Column("variant_id", sa.String(50), nullable=True),
        sa.Column("review_status", sa.String(100), nullable=True),
        sa.Column("condition_mim", sa.String(50), nullable=True),
        sa.Column("last_evaluated", sa.String(50), nullable=True),
        sa.Column("raw_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinvar_gene_name", "clinvar", ["gene_name"])
    op.create_index("ix_clinvar_mutation_str", "clinvar", ["mutation_str"])


def downgrade() -> None:
    op.drop_table("clinvar")
    op.drop_table("embeddings")
    op.drop_table("structures")
    op.drop_table("mutations")
    op.drop_table("proteins")
