"""Add crawl target runtime override columns

Revision ID: 9f1e2d3c4b5a
Revises: c8ea79f4b9d2
Create Date: 2026-03-04 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f1e2d3c4b5a"
down_revision: Union[str, Sequence[str], None] = "c8ea79f4b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("crawl_targets", sa.Column("headless", sa.Boolean(), nullable=True))
    op.add_column("crawl_targets", sa.Column("nav_timeout_ms", sa.Integer(), nullable=True))
    op.add_column("crawl_targets", sa.Column("max_attempts", sa.Integer(), nullable=True))
    op.add_column("crawl_targets", sa.Column("retry_sleep_ms", sa.Integer(), nullable=True))
    op.add_column(
        "crawl_targets", sa.Column("networkidle_timeout_ms", sa.Integer(), nullable=True)
    )
    op.add_column("crawl_targets", sa.Column("cookie_wait_ms", sa.Integer(), nullable=True))
    op.add_column("crawl_targets", sa.Column("cmp_wait_ms", sa.Integer(), nullable=True))
    op.add_column("crawl_targets", sa.Column("manual_wait_ms", sa.Integer(), nullable=True))

    op.create_check_constraint(
        op.f("ck_crawl_targets_check_nav_timeout_ms_positive"),
        "crawl_targets",
        "nav_timeout_ms IS NULL OR nav_timeout_ms > 0",
    )
    op.create_check_constraint(
        op.f("ck_crawl_targets_check_max_attempts_positive"),
        "crawl_targets",
        "max_attempts IS NULL OR max_attempts > 0",
    )
    op.create_check_constraint(
        op.f("ck_crawl_targets_check_retry_sleep_ms_positive"),
        "crawl_targets",
        "retry_sleep_ms IS NULL OR retry_sleep_ms > 0",
    )
    op.create_check_constraint(
        op.f("ck_crawl_targets_check_networkidle_timeout_ms_positive"),
        "crawl_targets",
        "networkidle_timeout_ms IS NULL OR networkidle_timeout_ms > 0",
    )
    op.create_check_constraint(
        op.f("ck_crawl_targets_check_cookie_wait_ms_positive"),
        "crawl_targets",
        "cookie_wait_ms IS NULL OR cookie_wait_ms > 0",
    )
    op.create_check_constraint(
        op.f("ck_crawl_targets_check_cmp_wait_ms_positive"),
        "crawl_targets",
        "cmp_wait_ms IS NULL OR cmp_wait_ms > 0",
    )
    op.create_check_constraint(
        op.f("ck_crawl_targets_check_manual_wait_ms_non_negative"),
        "crawl_targets",
        "manual_wait_ms IS NULL OR manual_wait_ms >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_crawl_targets_check_manual_wait_ms_non_negative"),
        "crawl_targets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crawl_targets_check_cmp_wait_ms_positive"),
        "crawl_targets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crawl_targets_check_cookie_wait_ms_positive"),
        "crawl_targets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crawl_targets_check_networkidle_timeout_ms_positive"),
        "crawl_targets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crawl_targets_check_retry_sleep_ms_positive"),
        "crawl_targets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crawl_targets_check_max_attempts_positive"),
        "crawl_targets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_crawl_targets_check_nav_timeout_ms_positive"),
        "crawl_targets",
        type_="check",
    )

    op.drop_column("crawl_targets", "manual_wait_ms")
    op.drop_column("crawl_targets", "cmp_wait_ms")
    op.drop_column("crawl_targets", "cookie_wait_ms")
    op.drop_column("crawl_targets", "networkidle_timeout_ms")
    op.drop_column("crawl_targets", "retry_sleep_ms")
    op.drop_column("crawl_targets", "max_attempts")
    op.drop_column("crawl_targets", "nav_timeout_ms")
    op.drop_column("crawl_targets", "headless")
