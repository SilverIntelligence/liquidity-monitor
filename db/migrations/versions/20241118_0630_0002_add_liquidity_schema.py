"""Add liquidity schema with v0.1 tables

Revision ID: 0002
Revises: 0001
Create Date: 2024-11-18 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create liquidity schema
    op.execute('CREATE SCHEMA IF NOT EXISTS liquidity')

    # liquidity.metrics_daily - daily metrics from various sources
    op.create_table(
        'metrics_daily',
        sa.Column('ds', sa.Date(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('metric', sa.String(100), nullable=False),
        sa.Column('value', sa.Numeric(20, 6), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ds', 'source', 'metric'),
        schema='liquidity'
    )
    op.create_index('ix_liquidity_metrics_daily_ds', 'metrics_daily', ['ds'], schema='liquidity')

    # liquidity.etf_flows - ETF daily flows
    op.create_table(
        'etf_flows',
        sa.Column('ds', sa.Date(), nullable=False),
        sa.Column('fund', sa.String(50), nullable=False),
        sa.Column('nav', sa.Numeric(20, 6), nullable=True),
        sa.Column('aum', sa.Numeric(20, 2), nullable=True),
        sa.Column('shares_in', sa.Numeric(20, 6), nullable=True),
        sa.Column('shares_out', sa.Numeric(20, 6), nullable=True),
        sa.Column('net_shares', sa.Numeric(20, 6), nullable=True),
        sa.Column('price', sa.Numeric(20, 6), nullable=True),
        sa.PrimaryKeyConstraint('ds', 'fund'),
        schema='liquidity'
    )
    op.create_index('ix_liquidity_etf_flows_ds', 'etf_flows', ['ds'], schema='liquidity')

    # liquidity.futures_positioning - futures OI and volume
    op.create_table(
        'futures_positioning',
        sa.Column('ds', sa.Date(), nullable=False),
        sa.Column('venue', sa.String(50), nullable=False),
        sa.Column('contract', sa.String(50), nullable=False),
        sa.Column('open_interest', sa.Numeric(20, 6), nullable=True),
        sa.Column('volume', sa.Numeric(20, 6), nullable=True),
        sa.PrimaryKeyConstraint('ds', 'venue', 'contract'),
        schema='liquidity'
    )
    op.create_index('ix_liquidity_futures_positioning_ds', 'futures_positioning', ['ds'], schema='liquidity')

    # liquidity.inventory - warehouse/vault inventory
    op.create_table(
        'inventory',
        sa.Column('ds', sa.Date(), nullable=False),
        sa.Column('venue', sa.String(50), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('tonnes_oz', sa.Numeric(20, 6), nullable=False),
        sa.Column('change_oz', sa.Numeric(20, 6), nullable=True),
        sa.PrimaryKeyConstraint('ds', 'venue', 'category'),
        schema='liquidity'
    )
    op.create_index('ix_liquidity_inventory_ds', 'inventory', ['ds'], schema='liquidity')

    # liquidity.index_hourly - the main liquidity index with hourly updates
    op.create_table(
        'index_hourly',
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('li_raw', sa.Numeric(10, 4), nullable=False),
        sa.Column('li_z', sa.Numeric(10, 4), nullable=False),
        sa.Column('components_json', postgresql.JSONB(), nullable=False),
        sa.Column('stale_components', postgresql.JSONB(), nullable=False, server_default="'{}'::jsonb"),
        sa.Column('version', sa.String(20), nullable=False, server_default="'v0'"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('ts'),
        schema='liquidity'
    )
    op.create_index('ix_liquidity_index_hourly_ts_desc', 'index_hourly', [sa.text('ts DESC')], schema='liquidity')

    # liquidity.etl_runs - ETL job tracking
    op.create_table(
        'etl_runs',
        sa.Column('etl_id', sa.String(100), nullable=False),
        sa.Column('job', sa.String(100), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('rows', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('etl_id'),
        schema='liquidity'
    )
    op.create_index('ix_liquidity_etl_runs_started_desc', 'etl_runs', [sa.text('started_at DESC')], schema='liquidity')
    op.create_index('ix_liquidity_etl_runs_job_source', 'etl_runs', ['job', 'source'], schema='liquidity')


def downgrade() -> None:
    op.drop_index('ix_liquidity_etl_runs_job_source', table_name='etl_runs', schema='liquidity')
    op.drop_index('ix_liquidity_etl_runs_started_desc', table_name='etl_runs', schema='liquidity')
    op.drop_table('etl_runs', schema='liquidity')
    op.drop_index('ix_liquidity_index_hourly_ts_desc', table_name='index_hourly', schema='liquidity')
    op.drop_table('index_hourly', schema='liquidity')
    op.drop_index('ix_liquidity_inventory_ds', table_name='inventory', schema='liquidity')
    op.drop_table('inventory', schema='liquidity')
    op.drop_index('ix_liquidity_futures_positioning_ds', table_name='futures_positioning', schema='liquidity')
    op.drop_table('futures_positioning', schema='liquidity')
    op.drop_index('ix_liquidity_etf_flows_ds', table_name='etf_flows', schema='liquidity')
    op.drop_table('etf_flows', schema='liquidity')
    op.drop_index('ix_liquidity_metrics_daily_ds', table_name='metrics_daily', schema='liquidity')
    op.drop_table('metrics_daily', schema='liquidity')
    op.execute('DROP SCHEMA IF EXISTS liquidity CASCADE')
