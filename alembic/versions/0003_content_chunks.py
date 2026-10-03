"""add story_content and chunks

Revision ID: 0003_content_chunks
Revises: 0002_add_domain
Create Date: 2025-01-01 00:02:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_content_chunks"
down_revision = "0002_add_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_content",
        sa.Column(
            "story_id",
            sa.Integer(),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "story_id",
            sa.Integer(),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=True),
        sa.UniqueConstraint("story_id", "chunk_index", name="uq_chunk_story_idx"),
    )
    op.create_index("ix_chunks_story_id", "chunks", ["story_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_story_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("story_content")
