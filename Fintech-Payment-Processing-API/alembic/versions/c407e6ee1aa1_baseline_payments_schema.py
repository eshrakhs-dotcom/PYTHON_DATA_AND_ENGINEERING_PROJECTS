"""baseline payments schema

Revision ID: c407e6ee1aa1
Revises:
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic uses these identifiers to determine migration order.
revision: str = "c407e6ee1aa1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the original payments table."""

    # Create the table with the six original payment fields.
    op.create_table(
        "payments",
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("merchant_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("payment_id"),
    )


def downgrade() -> None:
    """Undo the baseline migration."""

    # Remove the table if this migration is rolled back.
    op.drop_table("payments")
