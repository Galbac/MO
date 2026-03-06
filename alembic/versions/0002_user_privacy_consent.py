"""add user privacy consent fields"""

from alembic import op
import sqlalchemy as sa


revision = "0002_user_privacy_consent"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("privacy_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("privacy_consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "privacy_consent_at")
    op.drop_column("users", "privacy_consent")
