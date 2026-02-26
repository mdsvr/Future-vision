import yfinance as yf
import pandas as pd
import time
import requests
import json
import os
from logger import get_logger
from config import Config

logger = get_logger()

class MarketDataProvider:
    """
    Abstract base class for market data retrieval.
    Allows swapping between yfinance, Polygon, etc., without changing core logic.
    """
    def fetch(self, symbol, interval, period):
        raise NotImplementedError("Subclasses must implement fetch()")

class YFinanceProvider(MarketDataProvider):
    """
    Official yfinance provider.
    Handles MultiIndex edge cases and retries for stability.
    """
    def fetch(self, symbol, interval, period):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"[YFinance] Fetching {symbol} - Attempt {attempt + 1}")
                # We use progress=False to keep logs clean
                df = yf.download(symbol, interval=interval, period=period, progress=False)

                if df.empty:
                    logger.warning(f"[YFinance] Data for {symbol} is empty. Retrying...")
                    time.sleep(2)
                    continue

                # In some versions, yf returns a MultiIndex for columns. We flatten it.
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                # Standardize column names to lowercase for consistency
                df = df.rename(columns=str.lower)
                return df
            except Exception as e:
                logger.error(f"[YFinance] Network or API Error: {e}")
                time.sleep(2)
        return None

class PolygonProvider(MarketDataProvider):
    """
    Polygon.io Institutional Provider (Skeleton).
    Requires a valid POLYGON_API_KEY in .env.
    """
    def fetch(self, symbol, interval, period):
        if not Config.POLYGON_API_KEY:
            logger.error("[Polygon] API key missing. Check your .env file.")
            return None
        
        logger.info(f"[Polygon] Fetching {symbol}...")
        # Note: Aggregation bars implementation would be added here
        logger.warning("[Polygon] Provider not fully implemented. Falling back to default.")
        return None

def fetch_ohlcv(symbol: str) -> pd.DataFrame:
    """
    The main utility function for fetching and validating OHLCV data.
    Enforces minimum data requirements (200 rows) for technical indicators.
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)["data"]
    
    # Choose provider from config
    provider_name = config.get("market_data_provider", "yfinance")
    interval = config["interval"]
    period = config["period"]

    if provider_name == "polygon":
        provider = PolygonProvider()
    else:
        provider = YFinanceProvider()

    df = provider.fetch(symbol, interval, period)
    
    if df is not None:
        # --- Common Validation & Data Cleaning ---
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
             logger.error(f"Incomplete data columns. Found: {list(df.columns)}")
             return None
             
        # Drop rows with NaNs or zero volume (market closed or glitched data)
        df = df[required_cols].copy()
        df.dropna(inplace=True)
        df = df[df['volume'] > 0]
        
        # Ensure we have enough data to calculate EMA_200
        if len(df) < 200:
            logger.error(f"Incomplete data: Got {len(df)} rows, minimum required is 200.")
            return None
            
        logger.info(f"Verified {len(df)} valid market rows from {provider_name}.")
        return df

    return None