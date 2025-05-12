"""remove_payment_config_from_company

Revision ID: ec98b538722e
Revises: 5f263e239f42
Create Date: 2025-05-12 04:09:16.826641

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# If your models define JSON using sqlalchemy.dialects.postgresql, you might need:
# from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ec98b538722e"
down_revision: Union[str, None] = (
    "5f263e239f42"  # Make sure this 'Revises' ID is correct
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The payment_config column was removed from the Company model.
    # The database has confirmed this column does not exist (hence the previous error).
    # Therefore, no database operation is needed in this upgrade to make the
    # schema match the model regarding this specific column's absence.
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # If downgrading, we are conceptually going back to a model state
    # where payment_config existed, so we add the column back.
    op.add_column("companies", sa.Column("payment_config", sa.JSON(), nullable=True))
    # ### end Alembic commands ###
