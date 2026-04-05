"""
data_layer/live_market_feed.py
==============================
Responsible for downloading price history (OHLCV candles) asynchronously.
Integrates with Redis for caching to prevent API rate limits and reduce latency.
"""

import yfinance as yf
import pandas as pd
import time
import json
import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from logger import get_logger
from config import Config
from cache_layer.redis_manager import cache

logger = get_logger()

class MarketDataProvider:
    async def fetch(self, symbol, interval, period):
        raise NotImplementedError("Subclasses must implement async fetch()")

class YFinanceProvider(MarketDataProvider):
    """US stocks (AAPL, TSLA) via yfinance library. Wrapped in async."""
    async def fetch(self, symbol, interval, period):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"[YFinance] Fetching {symbol} - Attempt {attempt + 1}")
                # yfinance is synchronous, so we run it in a thread pool to avoid blocking the event loop
                df = await asyncio.to_thread(yf.download, symbol, interval=interval, period=period, progress=False)

                if df.empty:
                    logger.warning(f"[YFinance] Data for {symbol} is empty. Retrying...")
                    await asyncio.sleep(2)
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df = df.rename(columns=str.lower)
                df.index.name = "timestamp"
                return df
            except Exception as e:
                logger.error(f"[YFinance] Network or API Error: {e}")
                await asyncio.sleep(2)
        return None

class FyersProvider(MarketDataProvider):
    """
    Fyers API provider for Indian Equity markets (NSE, BSE).
    """
    INTERVAL_MAP = {
        "1m": "1", "2m": "2", "3m": "3", "5m": "5", "10m": "10", 
        "15m": "15", "20m": "20", "30m": "30", "60m": "60", "1h": "60", 
        "1d": "D", "1D": "D"
    }

    def __init__(self):
        try:
            from fyers_apiv3 import fyersModel
            self.fyersModel = fyersModel
        except ImportError:
            self.fyersModel = None
            logger.warning("[Fyers] fyers-apiv3 library not installed.")

    def _get_client(self):
        if not self.fyersModel or not Config.FYERS_APP_ID or not Config.FYERS_ACCESS_TOKEN:
            return None
        return self.fyersModel.FyersModel(
            client_id=Config.FYERS_APP_ID,
            is_async=False,
            token=Config.FYERS_ACCESS_TOKEN,
            log_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        )

    def _period_to_dates(self, period: str):
        today = datetime.today()
        period = period.lower()
        try:
            if period.endswith("d"): days = int(period[:-1])
            elif period.endswith("mo"): days = int(period[:-2]) * 30
            elif period.endswith("y"): days = int(period[:-1]) * 365
            else: days = 30
        except ValueError:
            logger.warning(f"Invalid period format: {period}. Defaulting to 30d.")
            days = 30
        start = today - timedelta(days=days)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    async def fetch(self, symbol, interval, period):
        client = self._get_client()
        if client is None:
            return None

        is_index = "-INDEX" in symbol.upper()

        async def _fetch_with_resolution(res, range_from, range_to):
            data = {
                "symbol": symbol, "resolution": res, "date_format":"1",
                "range_from": range_from, "range_to": range_to, "cont_flag": "1"
            }
            try:
                # Fyers SDK is blocking, run in thread
                response = await asyncio.to_thread(client.history, data=data)
                if response.get("s") != "ok":
                    logger.error(f"[Fyers] API Error response: {response}")
                    return None
                candles = response.get("candles", [])
                if not candles:
                    return None
                df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                df.set_index("timestamp", inplace=True)
                logger.info(f"[Fyers] Fetched {len(df)} candles for {symbol} (resolution={res})")
                return df
            except Exception as e:
                logger.error(f"[Fyers] Fetch error for {symbol}: {e}")
                return None

        fyers_resolution = self.INTERVAL_MAP.get(interval, "5")
        range_from, range_to = self._period_to_dates(period)
        
        df = await _fetch_with_resolution(fyers_resolution, range_from, range_to)

        if df is None and is_index and fyers_resolution != "D":
            logger.warning(f"[Fyers] Intraday data unavailable for index {symbol}. Retrying with daily...")
            daily_from, daily_to = self._period_to_dates("365d")
            df = await _fetch_with_resolution("D", daily_from, daily_to)

        return df

class AlphaVantageProvider(MarketDataProvider):
    """Alpha Vantage provider using native aiohttp."""
    BASE_URL = "https://www.alphavantage.co/query"
    INTRADAY_INTERVALS = {"1m", "5m", "15m", "30m", "60m", "1h"}
    AV_INTERVAL_MAP = {"1m":"1min", "5m":"5min", "15m":"15min", "30m":"30min", "60m":"60min", "1h":"60min"}

    async def fetch(self, symbol: str, interval: str, period: str):
        if not Config.ALPHAVANTAGE_API_KEY:
            return None

        if interval in self.INTRADAY_INTERVALS:
            av_interval = self.AV_INTERVAL_MAP.get(interval, "5min")
            params = {"function": "TIME_SERIES_INTRADAY", "symbol": symbol, "interval": av_interval, "outputsize": "compact", "datatype": "json", "apikey": Config.ALPHAVANTAGE_API_KEY}
            series_key = f"Time Series ({av_interval})"
        else:
            params = {"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact", "datatype": "json", "apikey": Config.ALPHAVANTAGE_API_KEY}
            series_key = "Time Series (Daily)"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    response.raise_for_status()
                    data = await response.json()

            if "Error Message" in data or "Note" in data or "Information" in data:
                return None

            time_series = data.get(series_key, {})
            if not time_series:
                return None

            records = []
            for timestamp_str, values in time_series.items():
                records.append({
                    "timestamp": pd.to_datetime(timestamp_str),
                    "open": float(values.get("1. open", 0)), "high": float(values.get("2. high", 0)),
                    "low": float(values.get("3. low", 0)), "close": float(values.get("4. close", 0)),
                    "volume": float(values.get("5. volume", values.get("6. volume", 0))),
                })

            df = pd.DataFrame(records)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
            return df
        except Exception as e:
            logger.error(f"[AlphaVantage] Async fetch error: {e}")
            return None

async def fetch_ohlcv(symbol: str) -> pd.DataFrame:
    """
    Async fetch and validate OHLCV data with Redis caching.
    """
    def load_config():
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        with open(config_path, "r") as f:
            return json.load(f)["data"]
    
    config = await asyncio.to_thread(load_config)
    
    provider_name = config.get("market_data_provider", "yfinance")
    interval = config.get("interval", "15m")
    period = config.get("period", "15d")
    
    # --- 1. Check Cache ---
    cache_key = f"ohlcv:{symbol}:{interval}:{period}:{provider_name}"
    cached_data = await cache.get(cache_key)
    
    if cached_data:
        logger.info(f"[Cache] Hit for {symbol} ({interval}). Serving from Redis/Memory.")
        df = pd.DataFrame(cached_data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        return df

    # --- 2. External Provider Fetch ---
    if provider_name == "fyers": provider = FyersProvider()
    elif provider_name == "alphavantage": provider = AlphaVantageProvider()
    else: provider = YFinanceProvider()

    t_start = time.time()
    df = await provider.fetch(symbol, interval, period)
    t_end = time.time()
    
    if df is not None:
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
             logger.warning(f"Missing required market columns: {missing}")
             return None
             
        df = df[required_cols].copy()
        df.dropna(inplace=True)

        is_index = "-INDEX" in symbol.upper()
        if not is_index:
            df = df[df['volume'] > 0]
        
        if len(df) < 200:
            logger.error(f"Incomplete data: Got {len(df)} rows, minimum required is 200.")
            return None
            
        logger.info(f"Verified {len(df)} valid market rows from {provider_name} in {(t_end-t_start)*1000:.0f}ms.")
        
        # --- 3. Save to Cache ---
        savable_df = df.reset_index()
        savable_df["timestamp"] = savable_df["timestamp"].astype(str)
        # Store for 60 seconds to prevent rate-limiting on same-minute refreshes
        await cache.set(cache_key, savable_df.to_dict(orient="records"), ttl_seconds=60)
        
        return df

    return None