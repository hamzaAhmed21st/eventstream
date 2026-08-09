"""Enforce the persisted metric contract.

Revision ID: 20260809_0002
Revises: 20260805_0001
Create Date: 2026-08-09 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_0002"
down_revision: str | None = "20260805_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUPPORTED_METRIC_NAMES_SQL = (
    "metric_name IN "
    "('latency_ms', 'request_count', 'error_count', 'cpu_usage', 'memory_usage')"
)
SERVICE_CONTRACT_SQL = (
    "service = lower(service) "
    "AND service !~ '^[[:space:]]' "
    "AND service !~ '[[:space:]]$' "
    "AND char_length(service) > 0"
)
VALUE_CONTRACT_SQL = (
    "(metric_name = 'latency_ms' AND value >= 0 AND value <= 86400000) OR "
    "(metric_name = 'request_count' AND value >= 0 AND value <= 1000000000 "
    "AND value = trunc(value)) OR "
    "(metric_name = 'error_count' AND value >= 0 AND value <= 1000000000 "
    "AND value = trunc(value)) OR "
    "(metric_name = 'cpu_usage' AND value >= 0 AND value <= 100) OR "
    "(metric_name = 'memory_usage' AND value >= 0 AND value <= 100)"
)


def upgrade() -> None:
    op.execute(
        f"""
        DO $eventstream_contract$
        DECLARE
            invalid_row_count bigint;
        BEGIN
            SELECT count(*)
            INTO invalid_row_count
            FROM metric_events
            WHERE NOT ({SUPPORTED_METRIC_NAMES_SQL})
               OR schema_version <> 1
               OR NOT ({SERVICE_CONTRACT_SQL})
               OR jsonb_typeof(tags) <> 'object'
               OR NOT ({VALUE_CONTRACT_SQL});

            IF invalid_row_count > 0 THEN
                RAISE EXCEPTION
                    'Cannot enforce the EventStream metric contract: % legacy rows are invalid',
                    invalid_row_count
                    USING HINT =
                        'Inspect and remediate those rows before rerunning the migration; '
                        'this migration does not alter or delete event data.';
            END IF;
        END
        $eventstream_contract$;
        """
    )
    op.create_check_constraint(
        "ck_metric_events_metric_name_supported",
        "metric_events",
        SUPPORTED_METRIC_NAMES_SQL,
    )
    op.create_check_constraint(
        "ck_metric_events_schema_version_supported",
        "metric_events",
        "schema_version = 1",
    )
    op.create_check_constraint(
        "ck_metric_events_service_normalized",
        "metric_events",
        SERVICE_CONTRACT_SQL,
    )
    op.create_check_constraint(
        "ck_metric_events_tags_object",
        "metric_events",
        "jsonb_typeof(tags) = 'object'",
    )
    op.create_check_constraint(
        "ck_metric_events_value_semantics",
        "metric_events",
        VALUE_CONTRACT_SQL,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_metric_events_value_semantics",
        "metric_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_metric_events_tags_object",
        "metric_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_metric_events_service_normalized",
        "metric_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_metric_events_schema_version_supported",
        "metric_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_metric_events_metric_name_supported",
        "metric_events",
        type_="check",
    )
