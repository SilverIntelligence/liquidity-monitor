# Precious Metals Liquidity Monitor

A comprehensive monitoring system for tracking liquidity metrics in precious metals markets (Gold and Silver).

## Overview

This system ingests data from multiple sources, computes normalized liquidity scores, and provides a 0-100 composite "Liquidity Index" for gold (XAU) and silver (XAG). The index combines:

- **Inventory levels** (COMEX, LBMA)
- **ETF flows** (GLD, IAU, SLV, SIVR)
- **Futures term structure** (CME)
- **CFTC positioning** (Commitments of Traders)
- **Dealer retail premiums** (over-spot pricing)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Ingestion  │────▶│  PostgreSQL  │────▶│   Scoring   │
│   Workers   │     │   + Redis    │     │   Engine    │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                      │
                           ▼                      ▼
                    ┌──────────────┐     ┌─────────────┐
                    │  FastAPI     │     │  Composite  │
                    │     API      │     │    Index    │
                    └──────────────┘     └─────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- Python 3.11+

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd app2
   ```

2. **Create environment file**
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

3. **Start services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Initialize the database**
   ```bash
   # Run migrations
   docker-compose exec api alembic upgrade head

   # Seed initial data
   docker-compose exec api python scripts/init_db.py
   ```

5. **Verify the system**
   ```bash
   # Check API health
   curl http://localhost:8000/health

   # Check system status
   curl http://localhost:8000/v1/status
   ```

## Development Setup

### Local Development (without Docker)

1. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

2. **Start PostgreSQL and Redis**
   ```bash
   # Using Docker for services only
   docker-compose up -d postgres redis
   ```

3. **Run migrations**
   ```bash
   alembic upgrade head
   ```

4. **Initialize database**
   ```bash
   python scripts/init_db.py
   ```

5. **Run the API**
   ```bash
   uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Run ingestors manually**
   ```bash
   # Run all ETF ingestors
   python scripts/run_ingestor.py --type etf

   # Run COMEX ingestors
   python scripts/run_ingestor.py --type comex

   # Run all ingestors
   python scripts/run_ingestor.py --type all
   ```

7. **Compute scores**
   ```bash
   python scripts/compute_scores.py
   ```

## API Endpoints

### Health & Status

- `GET /health` - Basic health check
- `GET /ready` - Readiness check with DB connectivity
- `GET /v1/status` - System status with last update times

### Liquidity Index

- `GET /v1/metal/{symbol}/index/latest` - Latest index for metal (XAU or XAG)
- `GET /v1/metal/{symbol}/index/history` - Historical index data
  - Query params: `start`, `end`, `interval`
- `GET /v1/metal/{symbol}/components/{component}/history` - Component history
  - Components: `inventory`, `etf_flow`, `term`, `cot`, `premium`

### Data Download

- `GET /v1/download/{symbol}/composite.csv` - Download CSV of composite index

### Example Requests

```bash
# Get latest Gold liquidity index
curl http://localhost:8000/v1/metal/XAU/index/latest

# Get Silver index history for last 30 days
curl "http://localhost:8000/v1/metal/XAG/index/history?start=2024-10-18&end=2024-11-18"

# Download Gold composite data as CSV
curl "http://localhost:8000/v1/download/XAU/composite.csv" -o gold_index.csv
```

## Data Sources

### ETF Holdings
- **GLD** (SPDR Gold Shares): Daily holdings in troy ounces
- **IAU** (iShares Gold Trust): Daily holdings
- **SLV** (iShares Silver Trust): Daily holdings
- **SIVR** (Aberdeen Silver ETF): Daily holdings

### Inventories
- **COMEX**: Daily warehouse stocks for gold and silver
- **LBMA**: Monthly vault holdings

### Futures & Derivatives
- **CME Futures**: Front-month settlements and term structure
- **CFTC CoT**: Weekly Commitments of Traders reports

### Retail Market
- **Dealer Premiums**: Hourly scraping of retail dealer over-spot prices

## Scoring Methodology

See [METHODOLOGY.md](METHODOLOGY.md) for detailed documentation.

### Component Scores (0-100)

Each component is normalized using:
1. Rolling window statistics (252 trading days default)
2. Z-score computation: `z = (value - mean) / std`
3. Percentile conversion: `percentile = Φ(z)`
4. Score: `round(percentile * 100)`

Direction adjustments:
- **Inventory**: Lower = tighter (direction = -1)
- **ETF flows**: Outflows = tighter (direction = -1)
- **Term structure**: Backwardation = tighter (direction = +1)
- **CoT**: Lower spec length = tighter (direction = -1)
- **Premiums**: Higher = tighter (direction = +1)

### Composite Index

Weighted average of component scores:

```
Liquidity Index = Σ(weight_i × score_i)

Default weights:
- Inventory: 0.25
- ETF flows: 0.20
- Term structure: 0.20
- CoT positioning: 0.20
- Dealer premiums: 0.15
```

**Interpretation:**
- **0-20**: Very loose liquidity
- **21-40**: Loose liquidity
- **41-60**: Neutral liquidity
- **61-80**: Tight liquidity
- **81-100**: Very tight liquidity

## Database Schema

Key tables:
- `metals`: Metal definitions (XAU, XAG)
- `sources`: Data source registry
- `series`: Time series definitions
- `observations`: Raw data points
- `scores`: Component scores
- `composites`: Composite liquidity indices
- `formula_versions`: Scoring formula versions
- `etl_runs`: Ingestion job tracking

## Monitoring & Operations

### Logs

```bash
# View API logs
docker-compose logs -f api

# View ingestion logs
docker-compose logs -f ingestion

# View cron logs
docker-compose exec ingestion tail -f /var/log/cron.log
```

### Metrics

The system tracks:
- ETL run status and duration
- HTTP response codes from data sources
- Data freshness (last update timestamps)
- Score computation latency

### Backfilling

To recompute historical scores:

```python
from datetime import datetime
from db.session import AsyncSessionLocal
from scoring.composite import recompute_historical_scores

async with AsyncSessionLocal() as session:
    result = await recompute_historical_scores(
        session=session,
        metal_id=1,  # Gold
        formula_id=1,
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2024, 11, 18)
    )
    print(result)
```

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Type checking
mypy .

# Linting
ruff check .
black --check .
```

## Configuration

Key environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `USER_AGENT`: User agent for web scraping
- `SCRAPE_DELAY_SECONDS`: Delay between dealer scrapes (default: 60)
- `CACHE_TTL_SECONDS`: API cache TTL (default: 300)

## Compliance

### Data Source Terms
- Respect `robots.txt` for all scraped sources
- Rate limit: 60 seconds between dealer scrapes
- Attribution: User agent identifies as "WallStreetSilver Liquidity Monitor"

### Known Limitations
- Dealer premium data requires manual verification of scraping selectors
- Some data sources may require authentication or paid APIs in production
- LBMA data is published monthly/quarterly (less frequent than daily)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run linters and type checks
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: See [METHODOLOGY.md](METHODOLOGY.md)
