"""add user product feature tables"""

from alembic import op
import sqlalchemy as sa


revision = "0003_user_product_features"
down_revision = "0002_user_privacy_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_reminders",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("remind_before_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="web"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], name=op.f("fk_match_reminders_match_id_matches")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_match_reminders_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_reminders")),
    )
    op.create_index(op.f("ix_match_reminders_user_id"), "match_reminders", ["user_id"], unique=False)
    op.create_index(op.f("ix_match_reminders_match_id"), "match_reminders", ["match_id"], unique=False)
    op.create_index(op.f("ix_match_reminders_channel"), "match_reminders", ["channel"], unique=False)

    op.create_table(
        "push_subscriptions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(length=1024), nullable=False),
        sa.Column("device_label", sa.String(length=255), nullable=True),
        sa.Column("keys_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("permission", sa.String(length=32), nullable=False, server_default="default"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_push_subscriptions_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_subscriptions")),
        sa.UniqueConstraint("endpoint", name=op.f("uq_push_subscriptions_endpoint")),
    )
    op.create_index(op.f("ix_push_subscriptions_user_id"), "push_subscriptions", ["user_id"], unique=False)
    op.create_index(op.f("ix_push_subscriptions_permission"), "push_subscriptions", ["permission"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_push_subscriptions_permission"), table_name="push_subscriptions")
    op.drop_index(op.f("ix_push_subscriptions_user_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

    op.drop_index(op.f("ix_match_reminders_channel"), table_name="match_reminders")
    op.drop_index(op.f("ix_match_reminders_match_id"), table_name="match_reminders")
    op.drop_index(op.f("ix_match_reminders_user_id"), table_name="match_reminders")
    op.drop_table("match_reminders")
