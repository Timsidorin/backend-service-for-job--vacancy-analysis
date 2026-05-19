"""add_candidate_profiles

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-03-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_profiles (
            user_uuid UUID NOT NULL PRIMARY KEY
                REFERENCES users (uuid) ON DELETE CASCADE,
            resume_file_name VARCHAR(512),
            mime_type VARCHAR(128),
            storage_path TEXT,
            extracted_text TEXT,
            profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            embedding vector(1536),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_candidate_profiles_updated_at
        ON candidate_profiles (updated_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS candidate_profiles")
