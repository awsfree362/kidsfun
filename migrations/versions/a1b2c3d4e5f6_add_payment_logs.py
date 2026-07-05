"""add payment_logs table

Revision ID: a1b2c3d4e5f6
Revises: 67ca3d24f4aa
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '67ca3d24f4aa'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payment_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('registration_id', sa.Integer(), nullable=False),
        sa.Column('gateway', sa.String(50), nullable=True),
        sa.Column('reference', sa.String(200), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['registration_id'], ['registrations.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('payment_logs')
