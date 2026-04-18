"""create legal_acts and articles tables

Revision ID: 20260418_0002
Revises: 20260418_0001
Create Date: 2026-04-18 15:40:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_0002"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_acts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sejm_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("kadencja", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sejm_id"),
    )
    op.create_index("ix_legal_acts_sejm_id", "legal_acts", ["sejm_id"], unique=False)

    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("act_id", sa.Uuid(), nullable=False),
        sa.Column("article_number", sa.String(length=100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["act_id"], ["legal_acts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_articles_act_id", "articles", ["act_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_articles_act_id", table_name="articles")
    op.drop_table("articles")

    op.drop_index("ix_legal_acts_sejm_id", table_name="legal_acts")
    op.drop_table("legal_acts")