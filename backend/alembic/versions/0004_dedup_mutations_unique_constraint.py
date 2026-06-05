"""Remove duplicate mutations and add unique constraint on gene_name+mutation_str

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete duplicate rows, keeping the lowest id for each (gene_name, mutation_str) pair
    op.execute("""
        DELETE FROM mutations
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM mutations
            GROUP BY gene_name, mutation_str
        )
    """)

    # Add unique constraint (idempotent — IF NOT EXISTS)
    op.execute("""
        ALTER TABLE mutations
        ADD CONSTRAINT uq_mutations_gene_mutation
        UNIQUE (gene_name, mutation_str)
    """)


def downgrade() -> None:
    op.drop_constraint("uq_mutations_gene_mutation", "mutations", type_="unique")
