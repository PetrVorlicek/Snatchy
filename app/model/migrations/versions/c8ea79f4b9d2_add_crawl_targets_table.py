"""Add crawl targets table

Revision ID: c8ea79f4b9d2
Revises: 61906c4153c8
Create Date: 2026-03-03 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8ea79f4b9d2"
down_revision: Union[str, Sequence[str], None] = "61906c4153c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "crawl_targets",
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=4096), nullable=False),
        sa.Column("parser_key", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("frequency_minutes", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "frequency_minutes > 0",
            name=op.f("ck_crawl_targets_check_frequency_minutes_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_crawl_targets_site_id_sites")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_targets")),
        sa.UniqueConstraint("url", name=op.f("uq_crawl_targets_url")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("crawl_targets")
