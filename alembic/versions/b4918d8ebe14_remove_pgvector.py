"""remove_pgvector

Revision ID: b4918d8ebe14
Revises: 0a9f118a0b9b
Create Date: 2026-08-01 14:47:47.031287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b4918d8ebe14'
down_revision: Union[str, None] = '0a9f118a0b9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_chunks_embedding_hnsw', table_name='chunks', postgresql_with={'m': '16', 'ef_construction': '64'}, postgresql_using='hnsw')
    op.drop_column('chunks', 'embedding')
    op.execute('DROP EXTENSION IF EXISTS vector;')
    op.add_column('chunks', sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True))


def downgrade() -> None:
    op.drop_column('chunks', 'embedding')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    import pgvector.sqlalchemy
    op.add_column('chunks', sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True))
    op.create_index('ix_chunks_embedding_hnsw', 'chunks', ['embedding'], unique=False, postgresql_with={'m': '16', 'ef_construction': '64'}, postgresql_using='hnsw')
