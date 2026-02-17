"""add agent runtime credentials table

Revision ID: a1d8e0679b3b
Revises: f4a8f4b6d921
Create Date: 2026-02-16 17:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1d8e0679b3b"
down_revision: Union[str, Sequence[str], None] = "f4a8f4b6d921"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create encrypted per-user runtime model credential storage."""
    op.create_table(
        "agent_runtime_credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("api_key_last4", sa.String(length=8), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("organization", sa.String(length=128), nullable=True),
        sa.Column(
            "use_vertex_ai",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("vertex_project", sa.String(length=128), nullable=True),
        sa.Column("vertex_location", sa.String(length=64), nullable=True),
        sa.Column("reasoning_mode", sa.String(length=16), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_agent_runtime_credentials_user_id"),
        "agent_runtime_credentials",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop encrypted runtime model credential storage."""
    op.drop_index(
        op.f("ix_agent_runtime_credentials_user_id"),
        table_name="agent_runtime_credentials",
    )
    op.drop_table("agent_runtime_credentials")
