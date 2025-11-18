# Data Source Compliance

## Overview

This document outlines compliance requirements, rate limiting, and terms of service for each data source used in the Liquidity Monitor.

## User Agent

All HTTP requests use the following User-Agent:
```
WallStreetSilver-LiquidityMonitor/0.1
```

## Data Sources

### ETF Holdings

#### GLD (SPDR Gold Shares)
- **URL**: https://www.spdrgoldshares.com
- **robots.txt**: Allows crawling
- **Rate Limit**: 1 request/hour (daily data)
- **Caching**: Raw CSV cached for 24 hours
- **Terms**: Public data, no authentication required
- **Attribution**: "Data sourced from SPDR Gold Shares"

#### SLV (iShares Silver Trust)
- **URL**: https://www.ishares.com
- **robots.txt**: Allows crawling with delays
- **Rate Limit**: 1 request/hour (daily data)
- **Caching**: Raw CSV cached for 24 hours
- **Terms**: Public data, no authentication required
- **Attribution**: "Data sourced from iShares"

#### PSLV (Sprott Physical Silver Trust)
- **URL**: https://sprott.com
- **robots.txt**: Allows crawling
- **Rate Limit**: 1 request/day
- **Caching**: Raw HTML cached for 24 hours
- **Terms**: Public data, no authentication required
- **Attribution**: "Data sourced from Sprott Physical Bullion Trusts"

### Inventory Data

#### COMEX
- **URL**: https://www.cmegroup.com/delivery_reports/
- **robots.txt**: Allows automated access
- **Rate Limit**: 1 request/day (daily reports published ~16:00 CT)
- **Caching**: Raw files cached permanently (historical data)
- **Terms**: Public data, CME Group Terms of Use apply
- **Attribution**: "Data sourced from CME Group"

#### LBMA (London Bullion Market Association)
- **URL**: https://www.lbma.org.uk
- **robots.txt**: Allows crawling
- **Rate Limit**: 1 request/day (monthly/quarterly updates)
- **Caching**: Raw data cached permanently
- **Terms**: Public data, LBMA website terms apply
- **Attribution**: "Data sourced from LBMA"

### Futures & Derivatives

#### CME Futures Settlement
- **URL**: https://www.cmegroup.com/CmeWS/mvc/Settlements/
- **robots.txt**: Allows automated access
- **Rate Limit**: 1 request/hour during trading hours
- **Caching**: Daily settlements cached for 7 days
- **Terms**: Public data, real-time data may require subscription
- **Attribution**: "Data sourced from CME Group"

#### CFTC Commitments of Traders
- **URL**: https://www.cftc.gov/MarketReports/CommitmentsofTraders/
- **robots.txt**: Allows crawling
- **Rate Limit**: 1 request/week (weekly reports published Fridays ~15:30 ET)
- **Caching**: Historical data cached permanently
- **Terms**: Public domain (US Government data)
- **Attribution**: "Data sourced from CFTC"

### Retail Dealer Premiums

#### APMEX
- **URL**: https://www.apmex.com
- **robots.txt**: Check `/robots.txt` - respect disallows
- **Rate Limit**: 1 request/60 seconds minimum between requests
- **Caching**: Price snapshots cached for 1 hour
- **Terms**: Scraping permitted for non-commercial research; check ToS
- **Attribution**: "Prices from APMEX"
- **Compliance**: Respect rate limits, identify as bot

#### JM Bullion
- **URL**: https://www.jmbullion.com
- **robots.txt**: Check `/robots.txt`
- **Rate Limit**: 1 request/60 seconds minimum
- **Caching**: Price snapshots cached for 1 hour
- **Terms**: Public pricing, check ToS for scraping policy
- **Attribution**: "Prices from JM Bullion"

#### SD Bullion
- **URL**: https://sdbullion.com
- **robots.txt**: Check `/robots.txt`
- **Rate Limit**: 1 request/60 seconds minimum
- **Caching**: Price snapshots cached for 1 hour
- **Terms**: Public pricing, check ToS
- **Attribution**: "Prices from SD Bullion"

## Rate Limiting Implementation

### Per-Source Throttling

```python
# Minimum delays between requests to same source
RATE_LIMITS = {
    "GLD": 3600,        # 1 hour
    "SLV": 3600,
    "PSLV": 86400,      # 24 hours
    "COMEX": 86400,
    "LBMA": 86400,
    "CME": 3600,
    "CFTC": 604800,     # 1 week
    "APMEX": 60,        # 1 minute
    "JMBullion": 60,
    "SDBullion": 60,
}
```

### Circuit Breaker

- After 3 consecutive failures, circuit opens for 60 minutes
- Prevents hammering sources during outages
- Logged in `liquidity.etl_runs` table

## Raw Data Storage

### When Allowed
- Store raw responses when ToS permits
- Used for:
  - Debugging parsing issues
  - Historical reconstruction
  - Checksumming for change detection

### Storage Location
- S3-compatible object storage (optional)
- Keyed by: `{source}/{date}/{checksum}.{ext}`
- Retention: 90 days for non-historical sources

## robots.txt Checking

Before deploying, verify robots.txt compliance:

```bash
curl https://www.apmex.com/robots.txt
curl https://www.jmbullion.com/robots.txt
curl https://sdbullion.com/robots.txt
```

Update selectors and delays accordingly.

## Attribution Requirements

### Web UI Footer
```
Data sourced from: CME Group, CFTC, LBMA, SPDR Gold Shares, iShares,
Sprott, APMEX, JM Bullion, SD Bullion
```

### API Responses
Include `data_sources` field listing active sources for each component.

## Compliance Monitoring

### Alerts
- Trigger alert if request rate exceeds configured limit
- Log all HTTP 429 (rate limit) responses
- Monitor for robots.txt violations

### Audit Trail
All requests logged in `liquidity.etl_runs`:
- Timestamp
- Source
- HTTP status
- Checksum of response

## Updates

Last reviewed: 2024-11-18

**Action Item**: Review quarterly and update as sources change ToS or robots.txt.
