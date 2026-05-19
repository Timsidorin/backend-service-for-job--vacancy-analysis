"""add_last_url_column

Revision ID: d1e2f3a4b5c6
Revises: c8d7e6f5a4b3
Create Date: 2026-02-27 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8d7e6f5a4b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ensure last_url column exists in vacancy_sources_state."""
    op.execute(
        """
        ALTER TABLE IF EXISTS vacancy_sources_state
        ADD COLUMN IF NOT EXISTS last_url TEXT
        """
    )


def downgrade() -> None:
    """Drop last_url column from vacancy_sources_state (if needed)."""
    op.execute(
        """
        ALTER TABLE IF EXISTS vacancy_sources_state
        DROP COLUMN IF EXISTS last_url
        """
    )

