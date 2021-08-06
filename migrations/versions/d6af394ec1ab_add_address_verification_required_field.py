"""Add address verification required field

Revision ID: d6af394ec1ab
Revises: 00ac5d537063
Create Date: 2021-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import text


revision = 'd6af394ec1ab'
down_revision = '00ac5d537063'
branch_labels = None
depends_on = None


def upgrade():
	op.add_column('server', sa.Column('address_verification_required', sa.Boolean(), nullable=False, server_default=text('0')))


def downgrade():
	op.drop_column('server', 'address_verification_required')
