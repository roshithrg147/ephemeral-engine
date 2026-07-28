"""0001_initial_security_foundation

Revision ID: 0001_initial_security_foundation
Revises: 
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial_security_foundation'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Application Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('firebase_uid', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'suspended', 'inactive')", name='ck_users_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_firebase_uid', 'users', ['firebase_uid'], unique=True)

    # 2. Tenants
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('identifier', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'suspended', 'inactive')", name='ck_tenants_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tenants_identifier', 'tenants', ['identifier'], unique=True)

    # 3. Tenant Memberships
    op.create_table(
        'tenant_memberships',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='viewer'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('viewer', 'operator', 'admin')", name='ck_tenant_memberships_role'),
        sa.CheckConstraint("status IN ('active', 'suspended', 'inactive')", name='ck_tenant_memberships_status'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tenant_id', name='uq_user_tenant_membership')
    )
    op.create_index('idx_memberships_lookup', 'tenant_memberships', ['user_id', 'tenant_id', 'status'], unique=False)

    # 4. Sessions
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(length=128), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('owner_user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('burned_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'burned', 'expired')", name='ck_sessions_status'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sessions_tenant_owner', 'sessions', ['tenant_id', 'owner_user_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_sessions_tenant_owner', table_name='sessions')
    op.drop_table('sessions')
    op.drop_index('idx_memberships_lookup', table_name='tenant_memberships')
    op.drop_table('tenant_memberships')
    op.drop_index('idx_tenants_identifier', table_name='tenants')
    op.drop_table('tenants')
    op.drop_index('idx_users_firebase_uid', table_name='users')
    op.drop_table('users')
