"""add_evaluation_detail_columns

Revision ID: 6feacf5c96f4
Revises: abc123
Create Date: 2026-03-14 22:25:53.750041

NOTE: These changes are now included in the base migration (80d8179e5c33).
This migration is kept as a no-op to preserve the Alembic revision chain.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6feacf5c96f4'
down_revision: Union[str, None] = 'abc123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Covered by base migration — no-op
    pass


def downgrade() -> None:
    # Covered by base migration — no-op
    pass
