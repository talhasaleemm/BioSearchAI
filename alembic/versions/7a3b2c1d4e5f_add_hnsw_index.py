"""add_hnsw_index

Revision ID: 7a3b2c1d4e5f
Revises: 
Create Date: 2026-07-22 04:13:35.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '7a3b2c1d4e5f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw "
        "(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw;")
