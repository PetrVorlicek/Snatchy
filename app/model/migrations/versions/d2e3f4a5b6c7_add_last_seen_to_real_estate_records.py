"""Add last_seen to real estate records

Revision ID: d2e3f4a5b6c7
Revises: f1c2d3e4a5b6
Create Date: 2026-03-04 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "f1c2d3e4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "real_estate_records",
        sa.Column("last_seen", sa.DateTime(), nullable=True),
    )
    op.execute(
        "UPDATE real_estate_records SET last_seen = published_at WHERE last_seen IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("real_estate_records", "last_seen")
