"""Add publication for Debezium CDC

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'dbz_publication') THEN
            CREATE PUBLICATION dbz_publication FOR TABLE raw_vacancies;
          END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP PUBLICATION IF EXISTS dbz_publication")
