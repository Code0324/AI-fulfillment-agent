"""add asin field to fulfillment_orders

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fulfillment_orders', sa.Column('asin', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('fulfillment_orders', 'asin')
