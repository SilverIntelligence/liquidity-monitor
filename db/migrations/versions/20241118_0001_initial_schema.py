"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-11-18 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums
    component_type = postgresql.ENUM(
        'inventory', 'etf_flow', 'term', 'cot', 'premium', 'fx',
        name='componenttype',
        create_type=True
    )
    component_type.create(op.get_bind(), checkfirst=True)

    frequency_type = postgresql.ENUM(
        'hourly', 'daily', 'weekly', 'monthly',
        name='frequencytype',
        create_type=True
    )
    frequency_type.create(op.get_bind(), checkfirst=True)

    etl_status = postgresql.ENUM(
        'running', 'success', 'failed', 'partial',
        name='etlstatus',
        create_type=True
    )
    etl_status.create(op.get_bind(), checkfirst=True)

    # Create metals table
    op.create_table(
        'metals',
        sa.Column('metal_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('metal_id'),
        sa.UniqueConstraint('symbol')
    )
    op.create_index('ix_metals_symbol', 'metals', ['symbol'])

    # Create sources table
    op.create_table(
        'sources',
        sa.Column('source_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=512), nullable=False),
        sa.Column('terms', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('source_id'),
        sa.UniqueConstraint('name')
    )

    # Create formula_versions table
    op.create_table(
        'formula_versions',
        sa.Column('formula_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('description', sa.String(length=512), nullable=False),
        sa.Column('weights', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('formula_id')
    )

    # Create series table
    op.create_table(
        'series',
        sa.Column('series_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metal_id', sa.Integer(), nullable=False),
        sa.Column('component', component_type, nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('freq', frequency_type, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['metal_id'], ['metals.metal_id']),
        sa.ForeignKeyConstraint(['source_id'], ['sources.source_id']),
        sa.PrimaryKeyConstraint('series_id')
    )
    op.create_index('ix_series_metal_component', 'series', ['metal_id', 'component'])

    # Create observations table
    op.create_table(
        'observations',
        sa.Column('series_id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(), nullable=False),
        sa.Column('v', sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('source_revision_ts', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['series_id'], ['series.series_id']),
        sa.PrimaryKeyConstraint('series_id', 'ts')
    )
    op.create_index('ix_observations_series_ts', 'observations', ['series_id', 'ts'])
    op.create_index('ix_observations_ts', 'observations', ['ts'])

    # Create scores table
    op.create_table(
        'scores',
        sa.Column('metal_id', sa.Integer(), nullable=False),
        sa.Column('component', component_type, nullable=False),
        sa.Column('ts', sa.DateTime(), nullable=False),
        sa.Column('s', sa.SmallInteger(), nullable=False),
        sa.Column('v', sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column('window', sa.JSON(), nullable=True),
        sa.Column('formula_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('s >= 0 AND s <= 100', name='scores_s_check'),
        sa.ForeignKeyConstraint(['formula_id'], ['formula_versions.formula_id']),
        sa.ForeignKeyConstraint(['metal_id'], ['metals.metal_id']),
        sa.PrimaryKeyConstraint('metal_id', 'component', 'ts')
    )
    op.create_index('ix_scores_metal_ts', 'scores', ['metal_id', 'ts'])
    op.create_index('ix_scores_ts', 'scores', ['ts'])

    # Create composites table
    op.create_table(
        'composites',
        sa.Column('metal_id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(), nullable=False),
        sa.Column('s', sa.SmallInteger(), nullable=False),
        sa.Column('components', sa.JSON(), nullable=False),
        sa.Column('formula_id', sa.Integer(), nullable=False),
        sa.Column('degraded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('s >= 0 AND s <= 100', name='composites_s_check'),
        sa.ForeignKeyConstraint(['formula_id'], ['formula_versions.formula_id']),
        sa.ForeignKeyConstraint(['metal_id'], ['metals.metal_id']),
        sa.PrimaryKeyConstraint('metal_id', 'ts')
    )
    op.create_index('ix_composites_metal_ts', 'composites', ['metal_id', 'ts'])
    op.create_index('ix_composites_ts', 'composites', ['ts'])

    # Create etl_runs table
    op.create_table(
        'etl_runs',
        sa.Column('etl_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', etl_status, nullable=False),
        sa.Column('rows', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.source_id']),
        sa.PrimaryKeyConstraint('etl_id')
    )
    op.create_index('ix_etl_runs_source_started', 'etl_runs', ['source_id', 'started_at'])

    # Create reddit_configs table
    op.create_table(
        'reddit_configs',
        sa.Column('config_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('subreddit', sa.String(length=50), nullable=False),
        sa.Column('metals', sa.JSON(), nullable=False),
        sa.Column('post_hour', sa.Integer(), nullable=False, server_default='12'),
        sa.Column('verbosity', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('alert_thresholds', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('post_hour >= 0 AND post_hour < 24', name='reddit_configs_post_hour_check'),
        sa.PrimaryKeyConstraint('config_id'),
        sa.UniqueConstraint('subreddit')
    )


def downgrade() -> None:
    op.drop_table('reddit_configs')
    op.drop_index('ix_etl_runs_source_started', table_name='etl_runs')
    op.drop_table('etl_runs')
    op.drop_index('ix_composites_ts', table_name='composites')
    op.drop_index('ix_composites_metal_ts', table_name='composites')
    op.drop_table('composites')
    op.drop_index('ix_scores_ts', table_name='scores')
    op.drop_index('ix_scores_metal_ts', table_name='scores')
    op.drop_table('scores')
    op.drop_index('ix_observations_ts', table_name='observations')
    op.drop_index('ix_observations_series_ts', table_name='observations')
    op.drop_table('observations')
    op.drop_index('ix_series_metal_component', table_name='series')
    op.drop_table('series')
    op.drop_table('formula_versions')
    op.drop_table('sources')
    op.drop_index('ix_metals_symbol', table_name='metals')
    op.drop_table('metals')

    # Drop enums
    sa.Enum(name='etlstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='frequencytype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='componenttype').drop(op.get_bind(), checkfirst=True)
