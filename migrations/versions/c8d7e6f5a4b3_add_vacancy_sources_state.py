"""add_vacancy_sources_state

Revision ID: c8d7e6f5a4b3
Revises: b7c8d9e0f1a2
Create Date: 2026-02-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8d7e6f5a4b3"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create vacancy_sources_state table for mining service."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vacancy_sources_state (
            source TEXT PRIMARY KEY,
            last_published_at TIMESTAMPTZ,
            last_url TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    """Drop vacancy_sources_state table."""
    op.execute("DROP TABLE IF EXISTS vacancy_sources_state")

