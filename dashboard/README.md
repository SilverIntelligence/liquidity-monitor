# Liquidity Monitor Dashboard

Next.js dashboard for visualizing precious metals liquidity metrics.

## Features

- **Overview**: Latest liquidity indices with component breakdowns and historical trends
- **ETF Flows**: Daily flow tracking for major gold/silver ETFs
- **Futures**: CME positioning, open interest, and term structure analysis
- **Real-time Updates**: Auto-refresh every minute
- **Degraded Mode**: Graceful handling of partial data

## Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Environment Variables

Create `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Pages

- `/` - Overview with liquidity cards and charts
- `/flows` - ETF flow analysis
- `/futures` - Futures market indicators

## Tech Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Recharts (charting library)
- Fetch API (no client secrets)

## Production

The dashboard is read-only and fetches data from the API. No authentication required.

```bash
docker-compose up -d dashboard
```

Access at: http://localhost:3000
