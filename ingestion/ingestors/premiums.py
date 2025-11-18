"""Dealer premium scraper for retail over-spot prices."""

import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ComponentType, FrequencyType, Metal, Series
from ingestion.base import Ingestor


class DealerPremiumIngestor(Ingestor):
    """Scrapes retail dealer premiums over spot for 1 oz coins/bars."""

    def __init__(self, metal_symbol: str) -> None:
        """Initialize dealer premium ingestor.

        Args:
            metal_symbol: Metal symbol ('XAU' for gold, 'XAG' for silver)
        """
        self.metal_symbol = metal_symbol

        # List of reputable dealers to scrape
        # Note: This is a template - actual implementation must respect robots.txt
        source_name = f"Dealer_Premium_{metal_symbol}"
        url = "https://aggregated-dealer-data.example.com"  # Placeholder

        super().__init__(source_name=source_name, source_url=url)
        self.series_id_cache: int | None = None

        # Define dealer URLs based on metal
        if metal_symbol == "XAU":
            self.dealers = [
                {
                    "name": "APMEX",
                    "url": "https://www.apmex.com/product/1/1-oz-american-gold-eagle-coin-bu-random-year",
                    "selector": ".product-price",
                },
                {
                    "name": "JMBullion",
                    "url": "https://www.jmbullion.com/1-oz-american-gold-eagle-coin/",
                    "selector": ".price",
                },
                {
                    "name": "SDBullion",
                    "url": "https://sdbullion.com/1-oz-american-gold-eagle-coin",
                    "selector": ".product-price",
                },
            ]
        else:  # Silver
            self.dealers = [
                {
                    "name": "APMEX",
                    "url": "https://www.apmex.com/product/19/1-oz-silver-round-generic",
                    "selector": ".product-price",
                },
                {
                    "name": "JMBullion",
                    "url": "https://www.jmbullion.com/one-ounce-silver-rounds/",
                    "selector": ".price",
                },
                {
                    "name": "SDBullion",
                    "url": "https://sdbullion.com/1-oz-silver-round",
                    "selector": ".product-price",
                },
            ]

    async def fetch_all_dealers(self) -> list[dict[str, Any]]:
        """Fetch prices from all dealers.

        Returns:
            List of dealer data with prices
        """
        import asyncio

        dealer_data = []

        for dealer in self.dealers:
            try:
                # Respect rate limits - wait between scrapes
                await asyncio.sleep(60)  # 60 second delay per dealer

                content, status = await self.fetch(dealer["url"])
                soup = BeautifulSoup(content, "html.parser")

                # Extract price using CSS selector
                price_elem = soup.select_one(dealer["selector"])
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    # Extract numeric value
                    price_match = re.search(r"\$?([\d,]+\.?\d*)", price_text)
                    if price_match:
                        price = float(price_match.group(1).replace(",", ""))
                        dealer_data.append(
                            {"name": dealer["name"], "price": price, "status": status}
                        )

            except Exception as e:
                # Log error but continue with other dealers
                dealer_data.append({"name": dealer["name"], "error": str(e)})

        return dealer_data

    async def parse(self, content: bytes) -> list[dict[str, Any]]:
        """Parse dealer premiums.

        Since we need to fetch multiple dealers, this method orchestrates
        the scraping and calculates median premium.

        Args:
            content: Not used for this ingestor

        Returns:
            List with single observation containing median premium
        """
        observations = []

        try:
            # Fetch from all dealers
            dealer_data = await self.fetch_all_dealers()

            # Get current spot price (simplified - in production, fetch from API)
            # For now, use approximate values
            spot_price = 2000.0 if self.metal_symbol == "XAU" else 25.0

            # Calculate premiums over spot
            premiums = []
            for dealer in dealer_data:
                if "price" in dealer:
                    premium_pct = ((dealer["price"] - spot_price) / spot_price) * 100
                    premiums.append(premium_pct)

            if premiums:
                # Calculate median premium
                import statistics

                median_premium = statistics.median(premiums)

                ts = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

                observations.append(
                    {
                        "ts": ts,
                        "v": median_premium,
                        "meta": {
                            "spot_price": spot_price,
                            "dealer_count": len(premiums),
                            "min_premium": min(premiums),
                            "max_premium": max(premiums),
                            "dealers": dealer_data,
                        },
                    }
                )

        except Exception as e:
            # Return empty on error
            pass

        return observations

    async def fetch(self, url: str | None = None) -> tuple[bytes, int]:
        """Override fetch to use the aggregated dealer URL if no specific URL given.

        Args:
            url: Specific dealer URL or None for default

        Returns:
            Tuple of (content, status_code)
        """
        if url is None:
            # If no URL specified, parse() will handle multi-dealer fetch
            return b"", 200

        return await super().fetch(url)

    async def run(self) -> dict[str, Any]:
        """Override run to handle multi-dealer fetching.

        Returns:
            Execution results
        """
        # Use custom logic since we fetch multiple URLs
        async with AsyncSessionLocal() as session:
            from db.models import ETLRun, ETLStatus
            from db.session import AsyncSessionLocal

            source_id = await self.ensure_source(session)

            etl_run = ETLRun(
                source_id=source_id, started_at=datetime.utcnow(), status=ETLStatus.RUNNING
            )
            session.add(etl_run)
            await session.commit()
            await session.refresh(etl_run)

            try:
                # Parse (which will fetch all dealers)
                observations = await self.parse(b"")

                # Get series_id
                series_id = await self.get_series_id(session)

                # Upsert observations
                rows = await self.upsert(session, series_id, observations)

                etl_run.finished_at = datetime.utcnow()
                etl_run.status = ETLStatus.SUCCESS
                etl_run.rows = rows
                await session.commit()

                return {
                    "status": "success",
                    "source": self.source_name,
                    "rows": rows,
                    "etl_id": etl_run.etl_id,
                }

            except Exception as e:
                etl_run.finished_at = datetime.utcnow()
                etl_run.status = ETLStatus.FAILED
                etl_run.error = str(e)
                await session.commit()

                return {"status": "failed", "source": self.source_name, "error": str(e)}

    async def get_series_id(self, session: AsyncSession) -> int:
        """Get or create series ID for dealer premiums."""
        if self.series_id_cache is not None:
            return self.series_id_cache

        # Get metal_id
        result = await session.execute(select(Metal).where(Metal.symbol == self.metal_symbol))
        metal = result.scalar_one_or_none()

        if metal is None:
            raise ValueError(f"Metal {self.metal_symbol} not found in database")

        # Get or create series
        result = await session.execute(
            select(Series).where(
                Series.metal_id == metal.metal_id,
                Series.component == ComponentType.PREMIUM,
                Series.source_id == self.source_id,
            )
        )
        series = result.scalar_one_or_none()

        if series is None:
            series = Series(
                metal_id=metal.metal_id,
                component=ComponentType.PREMIUM,
                unit="percent",
                freq=FrequencyType.HOURLY,
                source_id=self.source_id,
                description=f"Dealer median premium over spot for {self.metal_symbol}",
            )
            session.add(series)
            await session.commit()
            await session.refresh(series)

        self.series_id_cache = series.series_id
        return self.series_id_cache
