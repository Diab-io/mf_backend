"""equipment tonnage, new equipment statuses, user archived_at

Revision ID: 0003_equipment_tonnage_status
Revises: 0002_approval_audit_role
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_equipment_tonnage_status"
down_revision: Union[str, None] = "0002_approval_audit_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. tonnage
    op.add_column("equipment", sa.Column("tonnage", sa.Numeric(10, 2), nullable=True))

    # 2. user archiving
    op.add_column("users", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    # 3. replace equipment_status enum (Postgres cannot drop enum values in place)
    op.execute("ALTER TABLE equipment ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE equipment_status RENAME TO equipment_status_old")
    postgresql.ENUM(
        "actively_working", "idle", "under_maintenance", "off_hire", name="equipment_status"
    ).create(op.get_bind())
    op.execute(
        """
        ALTER TABLE equipment ALTER COLUMN status TYPE equipment_status USING (
            CASE status::text
                WHEN 'operational' THEN 'actively_working'
                WHEN 'out_of_service' THEN 'off_hire'
                ELSE status::text
            END
        )::equipment_status
        """
    )
    op.execute("ALTER TABLE equipment ALTER COLUMN status SET DEFAULT 'idle'")
    op.execute("DROP TYPE equipment_status_old")


def downgrade() -> None:
    op.execute("ALTER TABLE equipment ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE equipment_status RENAME TO equipment_status_new")
    postgresql.ENUM(
        "operational", "under_maintenance", "out_of_service", name="equipment_status"
    ).create(op.get_bind())
    op.execute(
        """
        ALTER TABLE equipment ALTER COLUMN status TYPE equipment_status USING (
            CASE status::text
                WHEN 'actively_working' THEN 'operational'
                WHEN 'idle' THEN 'operational'
                WHEN 'off_hire' THEN 'out_of_service'
                ELSE status::text
            END
        )::equipment_status
        """
    )
    op.execute("ALTER TABLE equipment ALTER COLUMN status SET DEFAULT 'operational'")
    op.execute("DROP TYPE equipment_status_new")

    op.drop_column("users", "archived_at")
    op.drop_column("equipment", "tonnage")
