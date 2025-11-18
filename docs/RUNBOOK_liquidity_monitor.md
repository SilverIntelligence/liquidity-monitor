# Liquidity Monitor Runbook

Operations guide for the Precious Metals Liquidity Monitor system.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Common Operations](#common-operations)
3. [Troubleshooting](#troubleshooting)
4. [Maintenance Procedures](#maintenance-procedures)
5. [Alerts and Thresholds](#alerts-and-thresholds)

## Architecture Overview

**Services:**
- `postgres`: PostgreSQL 15 database with `liquidity` schema
- `redis`: Redis 7 cache layer (TTL: 120-300s)
- `api`: FastAPI application (port 8000)
- `scheduler`: APScheduler with ETL jobs (hourly ETF, 15-min index compute)
- `dashboard`: Next.js 14 frontend (port 3000)

**Data Flow:**
1. Scheduler extracts data from sources (ETFs, COMEX, LBMA, CFTC, futures, dealer premiums)
2. Transformers normalize to oz/USD
3. Loaders upsert to `liquidity.*` tables
4. Index engine computes 0-100 liquidity score with stale detection
5. API serves cached JSON responses
6. Dashboard renders real-time metrics

## Common Operations

### Start/Stop Services

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart api
docker-compose restart scheduler
```

### View Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow specific service
docker-compose logs -f scheduler
docker-compose logs -f api

# Filter for specific job
docker-compose logs -f scheduler | grep '"job":"etf_flows"'

# Check for errors
docker-compose logs --tail=100 scheduler | grep '"level":"ERROR"'
```

### Check Service Health

```bash
# API health endpoint
curl -fsS http://localhost:8000/health

# API status (shows freshness)
curl -fsS http://localhost:8000/v1/status

# Check service healthchecks
docker-compose ps
```

## Troubleshooting

### Re-run Failed Hour

If an ETL job fails for a specific hour, manually trigger:

```bash
# Shell into scheduler container
docker-compose exec scheduler bash

# Run specific ETL job
python -m etl.jobs.hourly  # This will run immediately

# Or trigger backfill for specific date range
python -m etl.jobs.backfill --days 1
```

### Circuit Breaker Override

If a source is circuit-broken but you need to force a run:

```bash
# Restart scheduler to reset circuit breaker state
docker-compose restart scheduler

# Check logs to confirm circuit reset
docker-compose logs -f scheduler | grep circuit
```

**Circuit breaker thresholds:**
- Opens after: 3 consecutive failures
- Cooldown period: 60 minutes
- Logged events: `circuit_open`, `circuit_closed`, `circuit_retry`

### Stale Component Detection

When `stale_components` appears in index response:

```bash
# Check freshness of all sources
curl http://localhost:8000/v1/status | jq .

# Expected output includes last_updated times:
# {
#   "etf_flows": {"last_updated": "2024-11-18T14:00:00Z"},
#   "futures_positioning": {"last_updated": "2024-11-18T13:00:00Z"},
#   ...
# }
```

**Stale threshold:** >24 hours

**Resolution:**
1. Check scheduler logs for extraction failures
2. Verify source availability (websites may be down)
3. If source permanently unavailable, component weight is redistributed automatically

### Selector Drift Fix

If HTML/CSV selectors break due to source website changes:

1. **Identify broken extractor:**
   ```bash
   docker-compose logs scheduler | grep '"status":"failure"'
   ```

2. **Update extractor code:**
   - Edit `etl/extractors/extract_*.py`
   - Update CSS selectors, column names, or API endpoints
   - Test extraction locally

3. **Deploy fix:**
   ```bash
   git add etl/extractors/
   git commit -m "fix: Update extractor for [source] website changes"
   git push
   docker-compose build scheduler
   docker-compose restart scheduler
   ```

### Cache Flush

Clear Redis cache to force fresh API responses:

```bash
# Flush all cache keys
docker-compose exec redis redis-cli FLUSHALL

# Flush specific pattern
docker-compose exec redis redis-cli --scan --pattern "api:v1:*" | xargs docker-compose exec redis redis-cli DEL

# Check cache hit rate
docker-compose logs api | grep cache
```

### Database Connection Issues

```bash
# Check postgres is healthy
docker-compose exec postgres pg_isready -U postgres

# Connect to database
docker-compose exec postgres psql -U postgres -d liquidity_monitor

# Verify tables exist
\dt liquidity.*

# Check recent ETL runs
SELECT etl_id, job, source, status, finished_at
FROM liquidity.etl_runs
ORDER BY started_at DESC
LIMIT 10;
```

## Maintenance Procedures

### Run Backfill for Historical Data

Populate 30-90 days of historical data:

```bash
# 90-day backfill (recommended for initial setup)
docker-compose run --rm scheduler python -m etl.jobs.backfill --days 90

# 30-day backfill with custom delay
docker-compose run --rm scheduler python -m etl.jobs.backfill --days 30 --delay 120
```

**Backfill order:**
1. Inventory (COMEX/LBMA warehouse stocks)
2. ETF flows (GLD/SLV/PSLV)
3. Futures positioning (CME)
4. Index recompute (hourly)

**Notes:**
- Respects polite delays (60s default between sources)
- Idempotent upserts (safe to re-run)
- Logs progress every 24 hours

### Apply Database Migrations

When schema changes are needed:

```bash
# Generate new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Review migration file
cat db/migrations/versions/YYYYMMDD_HHMM_*_description.py

# Apply migration
docker-compose exec api alembic upgrade head

# Verify migration applied
docker-compose exec api alembic current

# Rollback if needed
docker-compose exec api alembic downgrade -1
```

**Migration best practices:**
1. Always review autogenerated migrations
2. Test on staging/local first
3. Backup database before production migrations
4. Use transactions for data migrations

### Update Formula Version

When changing index calculation methodology:

1. **Increment formula version:**
   ```sql
   INSERT INTO formula_versions (formula_id, name, description, created_at)
   VALUES (2, 'v1', 'Updated component weights', NOW());
   ```

2. **Update scoring engine:**
   - Edit `etl/index/compute.py`
   - Update `LiquidityIndexComputer` logic
   - Update default weights if needed

3. **Backfill with new formula:**
   ```bash
   # Recompute last 30 days with new formula
   docker-compose run --rm scheduler python -m etl.jobs.backfill --days 30
   ```

4. **Document in METHODOLOGY.md**

### Rotate Logs

Docker logs can grow large over time:

```bash
# Check log sizes
docker-compose ps -q | xargs docker inspect --format='{{.LogPath}}' | xargs ls -lh

# Rotate logs (requires docker restart)
docker-compose down
docker-compose up -d
```

Configure log rotation in `/etc/docker/daemon.json`:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## Alerts and Thresholds

### Recommended Alert Conditions

**Critical:**
- ETL tap failure ≥3 hours: Data source unavailable
- Freshness lag ≥6 hours: Index computation stalled
- API health check failing ≥5 minutes: Service down
- Database connection pool exhausted: Scale or restart needed

**Warning:**
- Missing component ≥24 hours: Stale data, degraded mode active
- Circuit breaker opened: Source temporarily disabled
- Cache hit rate <50%: Redis may be down or flushing too frequently

### Monitoring Queries

```sql
-- Check for stale data
SELECT ts, stale_components
FROM liquidity.index_hourly
WHERE stale_components != '{}'::jsonb
ORDER BY ts DESC
LIMIT 10;

-- ETL failure rate (last 24h)
SELECT job, source,
       COUNT(*) FILTER (WHERE status='failure') * 100.0 / COUNT(*) as failure_rate
FROM liquidity.etl_runs
WHERE started_at > NOW() - INTERVAL '24 hours'
GROUP BY job, source;

-- Index freshness
SELECT MAX(ts) as latest_index,
       EXTRACT(EPOCH FROM (NOW() - MAX(ts)))/3600 as hours_stale
FROM liquidity.index_hourly;
```

### Log Patterns

**Success patterns:**
```json
{"job": "etf_flows", "source": "GLD", "status": "success", "rows": 120}
{"job": "compute_index", "status": "success", "li_raw": 42.3, "stale": 0}
```

**Failure patterns:**
```json
{"job": "etf_flows", "source": "SLV", "status": "failure", "error": "HTTP 503"}
{"source": "GLD", "status": "circuit_open", "failures": 3}
```

## Emergency Contacts

- **On-call Engineer:** [TBD]
- **Data Source Issues:** Check docs/DATA_TAPS.md for source contacts
- **Database Admin:** [TBD]

## Related Documentation

- [METHODOLOGY.md](METHODOLOGY.md) - Scoring algorithm details
- [DATA_TAPS.md](DATA_TAPS.md) - Source compliance and rate limits
- [README.md](../README.md) - Installation and setup
