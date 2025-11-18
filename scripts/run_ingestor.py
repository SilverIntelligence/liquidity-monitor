"""Script to run data ingestors."""

import argparse
import asyncio
import sys
from datetime import datetime

from ingestion.ingestors import (
    GLDIngestor,
    IAUIngestor,
    SLVIngestor,
    SIVRIngestor,
    COMEXInventoryIngestor,
    LBMAInventoryIngestor,
    CFTCCoTIngestor,
    FuturesSettlementIngestor,
    DealerPremiumIngestor,
)


async def run_etf_ingestors() -> None:
    """Run all ETF ingestors."""
    print(f"[{datetime.utcnow()}] Running ETF ingestors...")

    ingestors = [
        GLDIngestor(),
        IAUIngestor(),
        SLVIngestor(),
        SIVRIngestor(),
    ]

    for ingestor in ingestors:
        try:
            result = await ingestor.run()
            print(f"[{datetime.utcnow()}] {ingestor.source_name}: {result}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR {ingestor.source_name}: {e}", file=sys.stderr)


async def run_comex_ingestors() -> None:
    """Run COMEX inventory ingestors."""
    print(f"[{datetime.utcnow()}] Running COMEX ingestors...")

    ingestors = [
        COMEXInventoryIngestor("XAU"),
        COMEXInventoryIngestor("XAG"),
    ]

    for ingestor in ingestors:
        try:
            result = await ingestor.run()
            print(f"[{datetime.utcnow()}] {ingestor.source_name}: {result}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR {ingestor.source_name}: {e}", file=sys.stderr)


async def run_lbma_ingestors() -> None:
    """Run LBMA inventory ingestors."""
    print(f"[{datetime.utcnow()}] Running LBMA ingestors...")

    ingestors = [
        LBMAInventoryIngestor("XAU"),
        LBMAInventoryIngestor("XAG"),
    ]

    for ingestor in ingestors:
        try:
            result = await ingestor.run()
            print(f"[{datetime.utcnow()}] {ingestor.source_name}: {result}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR {ingestor.source_name}: {e}", file=sys.stderr)


async def run_cftc_ingestors() -> None:
    """Run CFTC CoT ingestors."""
    print(f"[{datetime.utcnow()}] Running CFTC CoT ingestors...")

    ingestors = [
        CFTCCoTIngestor("XAU"),
        CFTCCoTIngestor("XAG"),
    ]

    for ingestor in ingestors:
        try:
            result = await ingestor.run()
            print(f"[{datetime.utcnow()}] {ingestor.source_name}: {result}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR {ingestor.source_name}: {e}", file=sys.stderr)


async def run_futures_ingestors() -> None:
    """Run futures settlement ingestors."""
    print(f"[{datetime.utcnow()}] Running futures settlement ingestors...")

    ingestors = [
        FuturesSettlementIngestor("XAU"),
        FuturesSettlementIngestor("XAG"),
    ]

    for ingestor in ingestors:
        try:
            result = await ingestor.run()
            print(f"[{datetime.utcnow()}] {ingestor.source_name}: {result}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR {ingestor.source_name}: {e}", file=sys.stderr)


async def run_premium_ingestors() -> None:
    """Run dealer premium ingestors."""
    print(f"[{datetime.utcnow()}] Running dealer premium ingestors...")

    ingestors = [
        DealerPremiumIngestor("XAU"),
        DealerPremiumIngestor("XAG"),
    ]

    for ingestor in ingestors:
        try:
            result = await ingestor.run()
            print(f"[{datetime.utcnow()}] {ingestor.source_name}: {result}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR {ingestor.source_name}: {e}", file=sys.stderr)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run data ingestors")
    parser.add_argument(
        "--type",
        required=True,
        choices=["etf", "comex", "lbma", "cftc", "futures", "premiums", "all"],
        help="Type of ingestor to run",
    )

    args = parser.parse_args()

    if args.type == "etf":
        await run_etf_ingestors()
    elif args.type == "comex":
        await run_comex_ingestors()
    elif args.type == "lbma":
        await run_lbma_ingestors()
    elif args.type == "cftc":
        await run_cftc_ingestors()
    elif args.type == "futures":
        await run_futures_ingestors()
    elif args.type == "premiums":
        await run_premium_ingestors()
    elif args.type == "all":
        await run_etf_ingestors()
        await run_comex_ingestors()
        await run_lbma_ingestors()
        await run_cftc_ingestors()
        await run_futures_ingestors()
        await run_premium_ingestors()


if __name__ == "__main__":
    asyncio.run(main())
