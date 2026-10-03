"""add domain to stories

Revision ID: 0002_add_domain
Revises: 0001_baseline
Create Date: 2025-01-01 00:01:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_domain"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("domain", sa.String(253), nullable=True))


def downgrade() -> None:
    op.drop_column("stories", "domain")
