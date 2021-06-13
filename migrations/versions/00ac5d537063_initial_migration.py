"""Initial migration

Revision ID: 00ac5d537063
Create Date: 2021-06-12
"""
from alembic import op
import sqlalchemy as sa


revision = '00ac5d537063'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
	op.create_table('server',
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('world_uuid', sa.String(length=36), nullable=True),
		sa.Column('online', sa.Boolean(), nullable=False),
		sa.Column('address', sa.String(), nullable=False),
		sa.Column('port', sa.Integer(), nullable=False),
		sa.Column('announce_ip', sa.String(), nullable=False),
		sa.Column('server_id', sa.String(), nullable=True),
		sa.Column('clients', sa.String(), nullable=True),
		sa.Column('clients_top', sa.Integer(), nullable=False),
		sa.Column('clients_max', sa.Integer(), nullable=False),
		sa.Column('first_seen', sa.DateTime(), nullable=False),
		sa.Column('start_time', sa.DateTime(), nullable=False),
		sa.Column('last_update', sa.DateTime(), nullable=False),
		sa.Column('total_uptime', sa.Float(), nullable=False),
		sa.Column('down_time', sa.DateTime(), nullable=True),
		sa.Column('game_time', sa.Integer(), nullable=False),
		sa.Column('lag', sa.Float(), nullable=True),
		sa.Column('ping', sa.Float(), nullable=False),
		sa.Column('mods', sa.String(), nullable=True),
		sa.Column('version', sa.String(), nullable=False),
		sa.Column('proto_min', sa.Integer(), nullable=False),
		sa.Column('proto_max', sa.Integer(), nullable=False),
		sa.Column('game_id', sa.String(), nullable=False),
		sa.Column('mapgen', sa.String(), nullable=True),
		sa.Column('url', sa.String(), nullable=True),
		sa.Column('default_privs', sa.String(), nullable=True),
		sa.Column('name', sa.String(), nullable=False),
		sa.Column('description', sa.String(), nullable=False),
		sa.Column('popularity', sa.Float(), nullable=False),
		sa.Column('geo_continent', sa.String(length=2), nullable=True),
		sa.Column('creative', sa.Boolean(), nullable=False),
		sa.Column('is_dedicated', sa.Boolean(), nullable=False),
		sa.Column('damage_enabled', sa.Boolean(), nullable=False),
		sa.Column('pvp_enabled', sa.Boolean(), nullable=False),
		sa.Column('password_required', sa.Boolean(), nullable=False),
		sa.Column('rollback_enabled', sa.Boolean(), nullable=False),
		sa.Column('can_see_far_names', sa.Boolean(), nullable=False),
		sa.PrimaryKeyConstraint('id')
	)
	op.create_index('ix_server_address_port', 'server', ['address', 'port'], unique=True)
	op.create_index(op.f('ix_server_online'), 'server', ['online'], unique=False)
	op.create_index(op.f('ix_server_world_uuid'), 'server', ['world_uuid'], unique=True)
	op.create_table('stats',
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('max_servers', sa.Integer(), nullable=False),
		sa.Column('max_clients', sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint('id')
	)


def downgrade():
	op.drop_table('stats')
	op.drop_index(op.f('ix_server_world_uuid'), table_name='server')
	op.drop_index(op.f('ix_server_online'), table_name='server')
	op.drop_index('ix_server_address_port', table_name='server')
	op.drop_table('server')
