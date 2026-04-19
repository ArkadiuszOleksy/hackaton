"""create news_items table

Revision ID: 20260418_0003
Revises: 20260418_0002
Create Date: 2026-04-18 16:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("link", sa.String(length=2000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link"),
    )
    op.create_index("ix_news_items_source_name", "news_items", ["source_name"], unique=False)
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_news_items_published_at", table_name="news_items")
    op.drop_index("ix_news_items_source_name", table_name="news_items")
    op.drop_table("news_items")