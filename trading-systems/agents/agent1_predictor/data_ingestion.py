"""
data_ingestion.py  —  Market Data Fetcher
==========================================
Responsible for downloading price history (OHLCV candles) for any stock.
This is the FIRST step in the analysis pipeline — everything else depends on this.

ARCHITECTURE — Provider Pattern:
  Instead of one hard-coded data source, we use swappable 'providers'.
  Each provider knows how to talk to one specific data source.
  main.py picks the right provider based on the market (India vs US).

  Providers available:
    YFinanceProvider  — US stocks (AAPL, TSLA, NVDA...) via yfinance library
    FyersProvider     — Indian stocks (NSE:RELIANCE-EQ, NSE:TCS-EQ...) via Fyers API

  Future providers can be added by subclassing MarketDataProvider.

OUTPUT FORMAT:
  All providers return a pandas DataFrame with lowercase columns:
    open  — Opening price of the candle
    high  — Highest price during the candle period
    low   — Lowest price during the candle period
    close — Closing price of the candle
    volume— Number of shares traded during the candle

PRE-REQUISITES FOR FYERS (Indian stocks):
  1. Create a Fyers API app at myapi.fyers.in
  2. Add FYERS_APP_ID, FYERS_SECRET_KEY to .env
  3. Run fyers_mcp_auth.py once per day to generate FYERS_ACCESS_TOKEN

Used by: main.py → fetch_data() → returns cleaned DataFrame
"""

import yfinance as yf
import pandas as pd
import time
import requests
import json
import os
from datetime import datetime, timedelta
from logger import get_logger
from config import Config

logger = get_logger()

class MarketDataProvider:
    """
    Abstract base class for market data retrieval.
    Allows swapping between yfinance, Fyers, Polygon, etc., without changing core logic.
    """
    def fetch(self, symbol, interval, period):
        raise NotImplementedError("Subclasses must implement fetch()")

class YFinanceProvider(MarketDataProvider):
    """
    Official yfinance provider for US stocks (NASDAQ, NYSE).
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

class FyersProvider(MarketDataProvider):
    """
    Fyers API provider for Indian Equity markets (NSE, BSE).
    
    Pre-requisites:
    - A Fyers trading account (https://fyers.in)
    - A Fyers API app created at myapi.fyers.in with your App ID and Secret
    - Add to .env: FYERS_APP_ID, FYERS_SECRET_KEY, FYERS_ACCESS_TOKEN
    
    Symbol Format (Fyers): "NSE:RELIANCE-EQ", "NSE:NIFTY50-INDEX"
    
    How to get access token:
     1. Run fyers_mcp_auth.py once to login via browser.
     2. It saves FYERS_ACCESS_TOKEN to your .env automatically.
     3. Tokens expire daily — re-run fyers_mcp_auth.py each morning.
    """

    # --- Fyers interval mapping ---
    # Fyers uses numeric strings for intraday (e.g. "5" = 5 min, "D" = daily)
    INTERVAL_MAP = {
        "1m": "1",
        "2m": "2",
        "3m": "3",
        "5m": "5",
        "10m": "10",
        "15m": "15",
        "20m": "20",
        "30m": "30",
        "60m": "60",
        "1h": "60",
        "1d": "D",
        "1D": "D",
    }

    def __init__(self):
        # Optional: Load fyers_apiv3 only if installed
        try:
            from fyers_apiv3 import fyersModel
            self.fyersModel = fyersModel
        except ImportError:
            self.fyersModel = None
            logger.warning("[Fyers] fyers-apiv3 library not installed. Run: pip install fyers-apiv3")

    def _get_client(self):
        """Creates and returns the authenticated Fyers API client."""
        if not self.fyersModel:
            return None
        if not Config.FYERS_APP_ID or not Config.FYERS_ACCESS_TOKEN:
            logger.error("[Fyers] FYERS_APP_ID or FYERS_ACCESS_TOKEN missing in .env")
            return None

        # Use App ID exactly as-is from myapi.fyers.in (e.g. "15QTK8NI7J-100")
        # Do NOT append -101 — the App ID already includes the app type suffix
        client = self.fyersModel.FyersModel(
            client_id=Config.FYERS_APP_ID,
            token=Config.FYERS_ACCESS_TOKEN,
            log_path=os.path.join(os.path.dirname(__file__), "logs")
        )
        return client

    def _period_to_dates(self, period: str):
        """
        Converts a period string (e.g. '15d', '1mo') to Fyers
        range_from / range_to date strings in 'YYYY-MM-DD' format.
        """
        today = datetime.today()
        period = period.lower()

        if period.endswith("d"):
            days = int(period[:-1])
        elif period.endswith("mo"):
            days = int(period[:-2]) * 30
        elif period.endswith("y"):
            days = int(period[:-1]) * 365
        else:
            days = 30  # Default fallback

        start = today - timedelta(days=days)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    def fetch(self, symbol, interval, period):
        """
        Fetches historical OHLCV candle data from Fyers for Indian market symbols.

        :param symbol: Fyers format, e.g. 'NSE:RELIANCE-EQ' or 'NSE:INDIA_VIX-INDEX'
        :param interval: time frame, e.g. '5m', '15m', '1d'
        :param period: lookback, e.g. '15d', '3mo'
        :return: cleaned OHLCV DataFrame or None

        NOTE: Some index symbols (e.g. INDIA_VIX) are only available at daily
        resolution on Fyers. If intraday fetch fails for an INDEX symbol, this
        method automatically retries with daily ('D') interval and 1-year lookback.
        """
        client = self._get_client()
        if client is None:
            return None

        is_index = "-INDEX" in symbol.upper()

        def _fetch_with_resolution(res, range_from, range_to):
            """Inner helper: fetch candles for a given resolution."""
            data = {
                "symbol":     symbol,
                "resolution": res,
                "date_format":"1",   # "1" = date string format (YYYY-MM-DD)
                "range_from": range_from,
                "range_to":   range_to,
                "cont_flag":  "1",   # "1" = include continuous data for futures
            }
            try:
                response = client.history(data=data)
                if response.get("s") != "ok":
                    logger.error(f"[Fyers] API Error response: {response}")
                    return None
                candles = response.get("candles", [])
                if not candles:
                    logger.warning(f"[Fyers] No candle data returned for {symbol}")
                    return None
                df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                df.set_index("timestamp", inplace=True)
                logger.info(f"[Fyers] Fetched {len(df)} candles for {symbol} (resolution={res})")
                return df
            except Exception as e:
                logger.error(f"[Fyers] Fetch error for {symbol}: {e}")
                return None

        # ── Primary fetch: use configured interval ─────────────────────────────
        fyers_resolution = self.INTERVAL_MAP.get(interval, "5")
        range_from, range_to = self._period_to_dates(period)
        logger.info(f"[Fyers] Fetching {symbol} | Interval: {fyers_resolution} | Range: {range_from} to {range_to}")

        df = _fetch_with_resolution(fyers_resolution, range_from, range_to)

        # ── Fallback: INDEX symbols often only have daily data ─────────────────
        # e.g. NSE:INDIA_VIX-INDEX, NSE:NIFTY50-INDEX — retry with daily + 1yr
        if df is None and is_index and fyers_resolution != "D":
            logger.warning(
                f"[Fyers] Intraday data unavailable for index {symbol}. "
                f"Retrying with daily (D) resolution over 1 year..."
            )
            daily_from, daily_to = self._period_to_dates("365d")
            df = _fetch_with_resolution("D", daily_from, daily_to)
            if df is not None:
                logger.info(f"[Fyers] Daily fallback succeeded for {symbol} ({len(df)} days)")

        return df

class AlphaVantageProvider(MarketDataProvider):
    """
    Alpha Vantage provider for US stock OHLCV data (NASDAQ, NYSE, etc.).
    
    Free Tier:
    - 25 API requests/day (standard free key)
    - 15-minute delayed intraday data
    - Full historical daily/weekly/monthly data
    
    Requires: ALPHAVANTAGE_API_KEY in .env
    API Reference: https://www.alphavantage.co/documentation/
    
    Symbol Format: Standard US ticker, e.g. "AAPL", "TSLA", "NVDA"
    """

    # Alpha Vantage function mapping by interval type
    # Intraday intervals use TIME_SERIES_INTRADAY; daily+ use different endpoint
    INTRADAY_INTERVALS = {"1m", "5m", "15m", "30m", "60m", "1h"}
    AV_INTERVAL_MAP = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "60m": "60min",
        "1h":  "60min",
    }

    BASE_URL = "https://www.alphavantage.co/query"

    def _period_to_outputsize(self, period: str) -> str:
        """
        Alpha Vantage free tier:
        - 'compact' = 100 most recent data points (FREE)
        - 'full'    = up to 20 years of data (PREMIUM only)
        We always use compact on the free tier key.
        """
        return "compact"

    def fetch(self, symbol: str, interval: str, period: str):
        """
        Fetches OHLCV data from Alpha Vantage REST API.
        
        :param symbol: US stock ticker, e.g. 'AAPL'
        :param interval: timeframe string, e.g. '5m', '1h', '1d'
        :param period: lookback window, e.g. '15d', '3mo', '1y'
        :return: cleaned OHLCV DataFrame or None
        """
        if not Config.ALPHAVANTAGE_API_KEY:
            logger.error("[AlphaVantage] ALPHAVANTAGE_API_KEY missing in .env")
            return None

        outputsize = self._period_to_outputsize(period)

        # --- Choose correct API function based on interval ---
        if interval in self.INTRADAY_INTERVALS:
            av_interval = self.AV_INTERVAL_MAP.get(interval, "5min")
            params = {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": av_interval,
                "outputsize": outputsize,
                "datatype": "json",
                "apikey": Config.ALPHAVANTAGE_API_KEY,
            }
            series_key = f"Time Series ({av_interval})"
        else:
            # Daily, weekly or monthly
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": outputsize,
                "datatype": "json",
                "apikey": Config.ALPHAVANTAGE_API_KEY,
            }
            series_key = "Time Series (Daily)"

        logger.info(f"[AlphaVantage] Fetching {symbol} | Interval: {interval} | Outputsize: {outputsize}")

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Alpha Vantage signals errors inside the JSON body
            if "Error Message" in data:
                logger.error(f"[AlphaVantage] API Error: {data['Error Message']}")
                return None
            if "Note" in data:
                logger.warning(f"[AlphaVantage] Rate limit hit: {data['Note']}")
                return None
            if "Information" in data:
                logger.warning(f"[AlphaVantage] API Info: {data['Information']}")
                return None

            time_series = data.get(series_key, {})
            if not time_series:
                logger.error(f"[AlphaVantage] No time series data found for key: '{series_key}'")
                return None

            # Build DataFrame — AV returns dict of {datetime_str: {OHLCV}}
            records = []
            for timestamp_str, values in time_series.items():
                records.append({
                    "timestamp": pd.to_datetime(timestamp_str),
                    "open":   float(values.get("1. open",   values.get("1. open",   0))),
                    "high":   float(values.get("2. high",   values.get("2. high",   0))),
                    "low":    float(values.get("3. low",    values.get("3. low",    0))),
                    "close":  float(values.get("4. close",  values.get("4. close",  0))),
                    "volume": float(values.get("5. volume", values.get("6. volume", 0))),
                })

            df = pd.DataFrame(records)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)  # Oldest first

            logger.info(f"[AlphaVantage] Fetched {len(df)} rows for {symbol}")
            return df

        except requests.exceptions.Timeout:
            logger.error("[AlphaVantage] Request timed out.")
            return None
        except Exception as e:
            logger.error(f"[AlphaVantage] Fetch error: {e}")
            return None

class PolygonProvider(MarketDataProvider):
    """
    Polygon.io Institutional Provider (Skeleton, US Markets).
    Requires a valid POLYGON_API_KEY in .env.
    """
    def fetch(self, symbol, interval, period):
        if not Config.POLYGON_API_KEY:
            logger.error("[Polygon] API key missing. Check your .env file.")
            return None
        
        logger.info(f"[Polygon] Fetching {symbol}...")
        logger.warning("[Polygon] Provider not fully implemented. Falling back to default.")
        return None

def fetch_ohlcv(symbol: str) -> pd.DataFrame:
    """
    The main utility function for fetching and validating OHLCV data.
    Enforces minimum data requirements (200 rows) for technical indicators.
    
    Provider selection via config.json → data.market_data_provider:
    - "yfinance"      : US stocks (default, no API key needed)
    - "alphavantage"  : US stocks via Alpha Vantage API (more reliable, 25 req/day free)
    - "fyers"         : Indian stocks (NSE/BSE, requires FYERS keys in .env)
    - "polygon"       : US stocks institutional (requires POLYGON_API_KEY)
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)["data"]
    
    # Choose provider from config
    provider_name = config.get("market_data_provider", "yfinance")
    interval = config["interval"]
    period = config["period"]

    if provider_name == "fyers":
        provider = FyersProvider()
    elif provider_name == "alphavantage":
        provider = AlphaVantageProvider()
    elif provider_name == "polygon":
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

        # Skip volume filter for INDEX symbols (VIX, NIFTY50 etc. have zero volume
        # because they are computed indices, not traded instruments)
        is_index = "-INDEX" in symbol.upper()
        if not is_index:
            df = df[df['volume'] > 0]   # For equities: drop market-closed / glitch rows
        
        # Ensure we have enough data to calculate EMA_200
        if len(df) < 200:
            logger.error(f"Incomplete data: Got {len(df)} rows, minimum required is 200.")
            return None
            
        logger.info(f"Verified {len(df)} valid market rows from {provider_name}.")
        return df

    return None