"""Add source_url to real estate records

Revision ID: f1c2d3e4a5b6
Revises: 9f1e2d3c4b5a
Create Date: 2026-03-04 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1c2d3e4a5b6"
down_revision: Union[str, Sequence[str], None] = "9f1e2d3c4b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "real_estate_records",
        sa.Column("source_url", sa.String(length=4096), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("real_estate_records", "source_url")
