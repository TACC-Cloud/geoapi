"""nullify_legacy_tokens


This notifies legacy streetview tokens. Should have been done in
9ca03b666aee

Revision ID: a1b2c3d4e5f6
Revises: 9ca03b666aee
Create Date: 2025-04-14 14:30:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9ca03b666aee"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE streetview
        SET token = NULL
        WHERE token_expires_at IS NULL AND token IS NOT NULL
    """
    )


def downgrade():
    # This operation is not reversible
    pass
