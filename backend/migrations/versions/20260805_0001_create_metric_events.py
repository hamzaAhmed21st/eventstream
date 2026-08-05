"""Create the metric_events table.

Revision ID: 20260805_0001
Revises:
Create Date: 2026-08-05 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service", sa.String(length=128), nullable=False),
        sa.Column("metric_name", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_metric_events"),
        sa.UniqueConstraint("event_id", name="uq_metric_events_event_id"),
    )
    op.create_index("ix_metric_events_service", "metric_events", ["service"], unique=False)
    op.create_index(
        "ix_metric_events_metric_name",
        "metric_events",
        ["metric_name"],
        unique=False,
    )
    op.create_index(
        "ix_metric_events_event_timestamp",
        "metric_events",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_metric_events_service_metric_timestamp",
        "metric_events",
        ["service", "metric_name", "event_timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_metric_events_service_metric_timestamp", table_name="metric_events")
    op.drop_index("ix_metric_events_event_timestamp", table_name="metric_events")
    op.drop_index("ix_metric_events_metric_name", table_name="metric_events")
    op.drop_index("ix_metric_events_service", table_name="metric_events")
    op.drop_table("metric_events")
