"""Create persistent log events and validated analyses."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "log_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("service", sa.String(255)),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_log_events_timestamp_id", "log_events", [sa.text("timestamp DESC"), sa.text("id DESC")])
    op.create_index("ix_log_events_source_timestamp", "log_events", ["source", sa.text("timestamp DESC")])
    op.create_index("ix_log_events_service_timestamp", "log_events", ["service", sa.text("timestamp DESC")])
    op.create_index("ix_log_events_severity_timestamp", "log_events", ["severity", sa.text("timestamp DESC")])
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("log_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("diagnosis", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_analyses_created_id", "analyses", [sa.text("created_at DESC"), sa.text("id DESC")])


def downgrade():
    op.drop_index("ix_analyses_created_id", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_log_events_severity_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_service_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_source_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_timestamp_id", table_name="log_events")
    op.drop_table("log_events")
