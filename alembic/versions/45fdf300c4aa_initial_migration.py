"""Initial migration

Revision ID: 45fdf300c4aa
Revises: 
Create Date: 2025-07-06 20:01:29.345765

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '45fdf300c4aa'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create projects table
    op.create_table('projects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('project_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'active', 'review', 'completed', 'archived')", name='check_project_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_project_created', 'projects', ['created_at'], unique=False)
    op.create_index('idx_project_status', 'projects', ['status'], unique=False)

    # Create products table
    op.create_table('products',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('model_no', sa.String(length=200), nullable=True),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('verified', sa.Boolean(), nullable=False),
        sa.Column('extraction_metadata', sa.JSON(), nullable=True),
        sa.Column('last_checked', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='check_confidence_range'),
        sa.CheckConstraint('qty > 0', name='check_qty_positive'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_product_confidence', 'products', ['confidence_score'], unique=False)
    op.create_index('idx_product_project', 'products', ['project_id'], unique=False)
    op.create_index('idx_product_type', 'products', ['type'], unique=False)
    op.create_index('idx_product_url', 'products', ['url'], unique=False)
    op.create_index('idx_product_verified', 'products', ['verified'], unique=False)

    # Create verification_requests table
    op.create_table('verification_requests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewer', sa.String(length=100), nullable=True),
        sa.Column('corrections', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('priority >= 1 AND priority <= 10', name='check_priority_range'),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'cancelled')", name='check_verification_status'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_verification_created', 'verification_requests', ['created_at'], unique=False)
    op.create_index('idx_verification_priority', 'verification_requests', ['priority'], unique=False)
    op.create_index('idx_verification_status', 'verification_requests', ['status'], unique=False)

    # Create change_history table
    op.create_table('change_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),
        sa.Column('field', sa.String(length=100), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("change_type IN ('added', 'removed', 'modified')", name='check_change_type'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_change_detected', 'change_history', ['detected_at'], unique=False)
    op.create_index('idx_change_product', 'change_history', ['product_id'], unique=False)

    # Create task_queue table
    op.create_table('task_queue',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('task_data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name='check_task_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_task_created', 'task_queue', ['created_at'], unique=False)
    op.create_index('idx_task_status', 'task_queue', ['status'], unique=False)
    op.create_index('idx_task_type', 'task_queue', ['task_type'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('task_queue')
    op.drop_table('change_history')
    op.drop_table('verification_requests')
    op.drop_table('products')
    op.drop_table('projects')