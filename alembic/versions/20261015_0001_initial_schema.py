"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = postgresql.ENUM("mechanic", "supervisor", "md", "admin", name="user_role", create_type=False)
    equipment_status = postgresql.ENUM(
        "operational", "under_maintenance", "out_of_service", name="equipment_status", create_type=False
    )
    fault_type = postgresql.ENUM(
        "corrective_maintenance", "preventive_maintenance", "emergency_repair", name="fault_type", create_type=False
    )
    priority = postgresql.ENUM("low", "medium", "high", "critical", name="priority", create_type=False)
    repair_status = postgresql.ENUM(
        "draft", "submitted", "pending_supervisor_approval", "supervisor_approved",
        "pending_md_approval", "approved", "repair_in_progress", "pending_parts",
        "repair_completed", "closed", "rejected_returned", "cancelled",
        name="repair_status", create_type=False,
    )
    approval_stage = postgresql.ENUM("supervisor", "md", name="approval_stage", create_type=False)
    approval_decision = postgresql.ENUM(
        "approve", "reject_return", "request_info", name="approval_decision", create_type=False
    )
    notification_type = postgresql.ENUM(
        "new_fault_report", "supervisor_approved", "md_approved", "request_more_info",
        "repair_completed", "critical_fault", "rejected",
        name="notification_type", create_type=False,
    )

    bind = op.get_bind()
    for enum_type in (
        user_role, equipment_status, fault_type, priority, repair_status,
        approval_stage, approval_decision, notification_type,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("site", sa.String(150), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "equipment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("equipment_type", sa.String(100), nullable=True),
        sa.Column("registration_number", sa.String(100), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("model_number", sa.String(100), nullable=True),
        sa.Column("capacity_spec", sa.String(255), nullable=True),
        sa.Column("current_location", sa.String(150), nullable=True),
        sa.Column("assigned_site", sa.String(150), nullable=True),
        sa.Column("status", equipment_status, nullable=False, server_default="operational"),
        sa.Column("last_maintenance_date", sa.Date(), nullable=True),
        sa.Column("next_maintenance_date", sa.Date(), nullable=True),
        sa.Column("total_maintenance_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_equipment_registration_number", "equipment", ["registration_number"], unique=True)

    op.create_table(
        "repair_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_number", sa.String(30), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("reported_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fault_detected_by", sa.String(150), nullable=True),
        sa.Column("assigned_mechanic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("fault_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fault_type", fault_type, nullable=False),
        sa.Column("priority", priority, nullable=False),
        sa.Column("fault_description", sa.Text(), nullable=False),
        sa.Column("repair_recommendation", sa.Text(), nullable=True),
        sa.Column("status", repair_status, nullable=False, server_default="draft"),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
    )
    op.create_index("ix_repair_requests_request_number", "repair_requests", ["request_number"], unique=True)
    op.create_index("ix_repair_requests_status", "repair_requests", ["status"])

    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("repair_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repair_requests.id"), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_attachments_stored_filename", "attachments", ["stored_filename"], unique=True)

    op.create_table(
        "approval_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("repair_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repair_requests.id"), nullable=False),
        sa.Column("stage", approval_stage, nullable=False),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", approval_decision, nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
    )

    op.create_table(
        "repair_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("repair_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repair_requests.id"), nullable=False),
        sa.Column("action_date", sa.Date(), nullable=False),
        sa.Column("action_taken", sa.Text(), nullable=False),
        sa.Column("parts_materials_used", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("labour_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("invoice_attachment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attachments.id"), nullable=True),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("repair_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repair_requests.id"), nullable=True),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("repair_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repair_requests.id"), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=True),
        sa.Column("detail", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("repair_actions")
    op.drop_table("approval_records")
    op.drop_table("attachments")
    op.drop_table("repair_requests")
    op.drop_table("equipment")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_name in (
        "notification_type", "approval_decision", "approval_stage", "repair_status",
        "priority", "fault_type", "equipment_status", "user_role",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
