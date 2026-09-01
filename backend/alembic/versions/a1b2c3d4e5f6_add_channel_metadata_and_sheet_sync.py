"""add channel_metadata and sheet sync fields to fulfillment_orders

Revision ID: a1b2c3d4e5f6
Revises: f3a9c1d7e802
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a9c1d7e802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fulfillment_orders', sa.Column('channel_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('fulfillment_orders', sa.Column('sheet_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('fulfillment_orders', sa.Column('sheet_sync_error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('fulfillment_orders', 'sheet_sync_error')
    op.drop_column('fulfillment_orders', 'sheet_synced_at')
    op.drop_column('fulfillment_orders', 'channel_metadata')
