"""add role capture to approval_records and audit_logs

Revision ID: 0002_approval_audit_role
Revises: 0001_initial
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_approval_audit_role"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = postgresql.ENUM(name="user_role", create_type=False)
    op.add_column("approval_records", sa.Column("decided_by_role", user_role, nullable=False, server_default="mechanic"))
    op.add_column("audit_logs", sa.Column("actor_role", user_role, nullable=False, server_default="mechanic"))
    op.alter_column("approval_records", "decided_by_role", server_default=None)
    op.alter_column("audit_logs", "actor_role", server_default=None)


def downgrade() -> None:
    op.drop_column("audit_logs", "actor_role")
    op.drop_column("approval_records", "decided_by_role")