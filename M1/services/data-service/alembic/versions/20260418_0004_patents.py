"""create patents table

Revision ID: 20260418_0004
Revises: 20260418_0003
Create Date: 2026-04-18 17:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_0004"
down_revision = "20260418_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("uprp_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uprp_id"),
    )
    op.create_index("ix_patents_uprp_id", "patents", ["uprp_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_patents_uprp_id", table_name="patents")
    op.drop_table("patents")