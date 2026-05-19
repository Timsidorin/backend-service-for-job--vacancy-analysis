"""add_embedding_to_processed_vacancies

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add embedding column to processed_vacancies (pgvector)."""
    # На всякий случай гарантируем, что расширение vector существует.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Добавляем nullable-колонку, чтобы можно было постепенно заполнять эмбеддинги.
    op.execute(
        """
        ALTER TABLE processed_vacancies
        ADD COLUMN IF NOT EXISTS embedding vector(1536)
        """
    )


def downgrade() -> None:
    """Remove embedding column from processed_vacancies."""
    op.execute(
        """
        ALTER TABLE processed_vacancies
        DROP COLUMN IF EXISTS embedding
        """
    )

