"""widen mutation change columns from varchar(50) to varchar(200)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("mutations", "charge_change",
                    type_=sa.String(200), existing_type=sa.String(50), existing_nullable=True)
    op.alter_column("mutations", "polarity_change",
                    type_=sa.String(200), existing_type=sa.String(50), existing_nullable=True)
    op.alter_column("mutations", "size_change",
                    type_=sa.String(200), existing_type=sa.String(50), existing_nullable=True)
    op.alter_column("mutations", "hydrophobicity_change",
                    type_=sa.String(200), existing_type=sa.String(50), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("mutations", "charge_change",
                    type_=sa.String(50), existing_type=sa.String(200), existing_nullable=True)
    op.alter_column("mutations", "polarity_change",
                    type_=sa.String(50), existing_type=sa.String(200), existing_nullable=True)
    op.alter_column("mutations", "size_change",
                    type_=sa.String(50), existing_type=sa.String(200), existing_nullable=True)
    op.alter_column("mutations", "hydrophobicity_change",
                    type_=sa.String(50), existing_type=sa.String(200), existing_nullable=True)
