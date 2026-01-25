"""add evidence versioning and access log

Revision ID: 1f9b8f4a7c31
Revises: 3c1e3b2a5d6f
Create Date: 2026-01-18 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision: str = "1f9b8f4a7c31"
down_revision: str | Sequence[str] | None = "3c1e3b2a5d6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema with evidence versioning and access audit tables."""
    op.create_table(
        "evidence_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("collector_version", sa.String(length=50), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("evidence_id", "version", name="uq_evidence_version"),
    )
    op.create_index(
        "ix_evidence_versions_evidence_id",
        "evidence_versions",
        ["evidence_id"],
    )
    op.create_index(
        "ix_evidence_versions_collected_at",
        "evidence_versions",
        ["collected_at"],
    )

    op.create_table(
        "evidence_access_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence.id"), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index(
        "ix_evidence_access_log_evidence_id",
        "evidence_access_log",
        ["evidence_id"],
    )
    op.create_index(
        "ix_evidence_access_log_timestamp",
        "evidence_access_log",
        ["timestamp"],
    )


def downgrade() -> None:
    """Downgrade schema by removing evidence versioning and access audit tables."""
    op.drop_index("ix_evidence_access_log_timestamp", table_name="evidence_access_log")
    op.drop_index("ix_evidence_access_log_evidence_id", table_name="evidence_access_log")
    op.drop_table("evidence_access_log")

    op.drop_index("ix_evidence_versions_collected_at", table_name="evidence_versions")
    op.drop_index("ix_evidence_versions_evidence_id", table_name="evidence_versions")
    op.drop_table("evidence_versions")
