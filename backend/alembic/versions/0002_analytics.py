"""Add search_count and last_searched to proteins; add composite index on mutations

Revision ID: 0002_analytics
Revises: 0001_initial
Create Date: 2026-01-02 00:00:00.000000

This migration demonstrates:
- Adding columns safely with server defaults (no table lock on large datasets)
- Adding a composite index for common query patterns
- Reversible downgrade
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_analytics"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Track how often each protein is queried (useful for cache warming)
    op.add_column(
        "proteins",
        sa.Column(
            "search_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "proteins",
        sa.Column("last_searched_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Composite index: the most common query pattern is gene_name + mutation_str together
    op.create_index(
        "ix_mutations_gene_mutation",
        "mutations",
        ["gene_name", "mutation_str"],
        unique=True,
    )

    # Index clinical significance for fast pathogenic filtering
    op.create_index(
        "ix_clinvar_significance",
        "clinvar",
        ["clinical_significance"],
    )


def downgrade() -> None:
    op.drop_index("ix_clinvar_significance", table_name="clinvar")
    op.drop_index("ix_mutations_gene_mutation", table_name="mutations")
    op.drop_column("proteins", "last_searched_at")
    op.drop_column("proteins", "search_count")
