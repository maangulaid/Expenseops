"""Initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2026-01-15 12:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums first
    op.execute("CREATE TYPE receiptstatus AS ENUM ('QUEUED', 'PROCESSING', 'COMPLETED', 'FLAGGED', 'FAILED')")
    op.execute("CREATE TYPE policyseverity AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')")
    op.execute("CREATE TYPE ticketstatus AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')")
    op.execute("CREATE TYPE ticketpriority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT')")

    # Now create enum objects with create_type=False to avoid recreating
    receipt_status_enum = postgresql.ENUM('QUEUED', 'PROCESSING', 'COMPLETED', 'FLAGGED', 'FAILED', name='receiptstatus', create_type=False)
    policy_severity_enum = postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='policyseverity', create_type=False)
    ticket_status_enum = postgresql.ENUM('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', name='ticketstatus', create_type=False)
    ticket_priority_enum = postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'URGENT', name='ticketpriority', create_type=False)

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_roles_id', 'roles', ['id'])
    op.create_index('ix_roles_name', 'roles', ['name'])

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])

    # Create user_roles junction table
    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role')
    )
    op.create_index('ix_user_roles_id', 'user_roles', ['id'])

    # Create receipts table
    op.create_table(
        'receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('source_sha256', sa.String(length=64), nullable=False),
        sa.Column('minio_key', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('status', receipt_status_enum, nullable=False, server_default='QUEUED'),
        sa.Column('processing_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('merchant_name', sa.String(length=255), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('transaction_date', sa.Date(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True, server_default='USD'),
        sa.Column('raw_ocr_text', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'source_sha256', name='uq_user_receipt_hash')
    )
    op.create_index('ix_receipts_id', 'receipts', ['id'])
    op.create_index('ix_receipts_user_id', 'receipts', ['user_id'])
    op.create_index('ix_receipts_source_sha256', 'receipts', ['source_sha256'])
    op.create_index('ix_receipts_status', 'receipts', ['status'])
    op.create_index('ix_receipts_processing_version', 'receipts', ['processing_version'])
    op.create_index('idx_receipts_user_status', 'receipts', ['user_id', 'status'])
    op.create_index('idx_receipts_uploaded_at_desc', 'receipts', [sa.text('uploaded_at DESC')])

    # Create receipt_events table
    op.create_table(
        'receipt_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receipt_id', sa.Integer(), nullable=False),
        sa.Column('from_status', receipt_status_enum, nullable=True),
        sa.Column('to_status', receipt_status_enum, nullable=False),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('event_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.Column('triggered_by_system', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_receipt_events_id', 'receipt_events', ['id'])
    op.create_index('ix_receipt_events_receipt_id', 'receipt_events', ['receipt_id'])
    op.create_index('idx_receipt_events_correlation', 'receipt_events', ['correlation_id'])
    op.create_index('idx_receipt_events_created_at_desc', 'receipt_events', [sa.text('created_at DESC')])
    op.create_index('idx_receipt_events_event_type', 'receipt_events', ['event_type'])

    # Create idempotency_keys table
    op.create_table(
        'idempotency_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('ix_idempotency_keys_id', 'idempotency_keys', ['id'])
    op.create_index('ix_idempotency_keys_key', 'idempotency_keys', ['key'])
    op.create_index('idx_idempotency_expires', 'idempotency_keys', ['expires_at'])

    # Create policy_rules table
    op.create_table(
        'policy_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('severity', policy_severity_enum, nullable=False, server_default='MEDIUM'),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_policy_rules_id', 'policy_rules', ['id'])
    op.create_index('ix_policy_rules_code', 'policy_rules', ['code'])
    op.create_index('ix_policy_rules_is_active', 'policy_rules', ['is_active'])

    # Create tickets table (before policy_evaluations since it's referenced)
    op.create_table(
        'tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receipt_id', sa.Integer(), nullable=True),
        sa.Column('ticket_type', sa.String(length=50), nullable=False),
        sa.Column('priority', ticket_priority_enum, nullable=False, server_default='MEDIUM'),
        sa.Column('status', ticket_status_enum, nullable=False, server_default='OPEN'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('ticket_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tickets_id', 'tickets', ['id'])
    op.create_index('ix_tickets_receipt_id', 'tickets', ['receipt_id'])
    op.create_index('ix_tickets_ticket_type', 'tickets', ['ticket_type'])
    op.create_index('ix_tickets_assigned_to_user_id', 'tickets', ['assigned_to_user_id'])
    op.create_index('idx_tickets_status', 'tickets', ['status'])
    op.create_index('idx_tickets_created_at_desc', 'tickets', [sa.text('created_at DESC')])
    op.create_index('idx_tickets_correlation', 'tickets', ['correlation_id'])

    # Create policy_evaluations table
    op.create_table(
        'policy_evaluations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receipt_id', sa.Integer(), nullable=False),
        sa.Column('policy_rule_id', sa.Integer(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['policy_rule_id'], ['policy_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_policy_evaluations_id', 'policy_evaluations', ['id'])
    op.create_index('ix_policy_evaluations_receipt_id', 'policy_evaluations', ['receipt_id'])
    op.create_index('idx_policy_evals_passed', 'policy_evaluations', ['passed'])
    op.create_index('idx_policy_evals_correlation', 'policy_evaluations', ['correlation_id'])

    # Seed default roles
    op.execute("""
        INSERT INTO roles (name, description) VALUES
        ('user', 'Regular user - can upload and view own receipts'),
        ('support', 'Support staff - can view all receipts and tickets, reprocess receipts'),
        ('admin', 'Administrator - full access including policy management')
    """)

    # Seed default policy rules
    op.execute("""
        INSERT INTO policy_rules (code, name, description, severity, config, is_active) VALUES
        ('MAX_AMOUNT', 'Maximum Amount Check', 'Flags receipts exceeding configured amount threshold', 'HIGH', '{"max_amount": 1000.00}'::jsonb, true),
        ('DUPLICATE_RECEIPT', 'Duplicate Receipt Detection', 'Detects potential duplicate receipts within time window', 'MEDIUM', '{"look_back_days": 90}'::jsonb, true),
        ('MISSING_MERCHANT', 'Missing Merchant Name', 'Flags receipts where merchant name could not be extracted', 'LOW', '{"required": true}'::jsonb, true)
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('policy_evaluations')
    op.drop_table('tickets')
    op.drop_table('policy_rules')
    op.drop_table('idempotency_keys')
    op.drop_table('receipt_events')
    op.drop_table('receipts')
    op.drop_table('user_roles')
    op.drop_table('users')
    op.drop_table('roles')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS receiptstatus')
    op.execute('DROP TYPE IF EXISTS policyseverity')
    op.execute('DROP TYPE IF EXISTS ticketstatus')
    op.execute('DROP TYPE IF EXISTS ticketpriority')
