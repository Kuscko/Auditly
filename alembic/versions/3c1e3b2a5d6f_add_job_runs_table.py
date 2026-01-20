"""add job_runs table

Revision ID: 3c1e3b2a5d6f
Revises: b297497b0925
Create Date: 2026-01-08 00:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "3c1e3b2a5d6f"

# Adjust this to the actual previous revision in your repo
down_revision = "b297497b0925"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=100), nullable=False, index=True),
        sa.Column("environment", sa.String(length=50), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_table("job_runs")
