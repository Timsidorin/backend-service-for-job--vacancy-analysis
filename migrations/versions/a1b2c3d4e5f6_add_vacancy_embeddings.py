"""add_vacancy_embeddings

Revision ID: a1b2c3d4e5f6
Revises: 9d1e392ae7c2
Create Date: 2026-02-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9d1e392ae7c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pgvector extension and vacancy_embeddings table."""
    # pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Таблица для эмбеддингов вакансий.
    # processed_uuid ссылается на processed_vacancies.uuid
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vacancy_embeddings (
            processed_uuid UUID PRIMARY KEY
                REFERENCES processed_vacancies (uuid)
                ON DELETE CASCADE,
            embedding vector(1536) NOT NULL
        )
        """
    )


def downgrade() -> None:
    """Drop vacancy_embeddings table (не трогаем extension vector)."""
    op.execute("DROP TABLE IF EXISTS vacancy_embeddings")

