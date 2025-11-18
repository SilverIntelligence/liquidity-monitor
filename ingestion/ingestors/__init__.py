"""Data ingestor implementations."""

from ingestion.ingestors.etf import GLDIngestor, IAUIngestor, SLVIngestor, SIVRIngestor
from ingestion.ingestors.comex import COMEXInventoryIngestor
from ingestion.ingestors.lbma import LBMAInventoryIngestor
from ingestion.ingestors.cftc import CFTCCoTIngestor
from ingestion.ingestors.futures import FuturesSettlementIngestor
from ingestion.ingestors.premiums import DealerPremiumIngestor

__all__ = [
    "GLDIngestor",
    "IAUIngestor",
    "SLVIngestor",
    "SIVRIngestor",
    "COMEXInventoryIngestor",
    "LBMAInventoryIngestor",
    "CFTCCoTIngestor",
    "FuturesSettlementIngestor",
    "DealerPremiumIngestor",
]
