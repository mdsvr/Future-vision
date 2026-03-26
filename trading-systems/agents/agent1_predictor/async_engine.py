"""
async_engine.py  —  Asynchronous Parallel Execution Pipeline
=============================================================
Provides a high-performance async wrapper around the synchronous
data & feature computation pipeline. Uses ThreadPoolExecutor for
CPU-bound pandas/numpy work (which cannot use asyncio natively).

TARGET EXECUTION FLOW:
  Client Request
    → fetch_ohlcv  (async, thread pool)
    → compute_features (async, thread pool)
    → classify_regime + generate_signals (same thread, fast CPU work)
    → return result dict

USAGE:
    import asyncio
    from async_engine import run_pipeline_async

    # Single symbol:
    result = asyncio.run(run_pipeline_async("AAPL"))

    # Multiple symbols in parallel:
    results = asyncio.run(run_pipeline_multi(["AAPL", "TSLA", "NVDA"]))

PERFORMANCE NOTES:
    - First run: no cache benefit (cold start)
    - Same symbol within TTL_SECONDS: returns cached features instantly
    - 3 symbols in parallel: ~3× faster than sequential
"""

import asyncio
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# ── Cache Configuration ────────────────────────────────────────────────────────
TTL_SECONDS = 60          # Cached feature DataFrames expire after 60 seconds
_feature_cache: dict = {}  # {symbol -> (timestamp, df)}


def _get_cached_features(symbol: str):
    """Returns cached feature DataFrame if within TTL, else None."""
    if symbol in _feature_cache:
        cached_time, cached_df = _feature_cache[symbol]
        if time.time() - cached_time < TTL_SECONDS:
            logger.info(f"[AsyncEngine] Cache HIT for {symbol} (age: {time.time() - cached_time:.1f}s)")
            return cached_df
        else:
            del _feature_cache[symbol]
    return None


def _store_cached_features(symbol: str, df):
    """Stores a feature DataFrame into the in-memory cache."""
    _feature_cache[symbol] = (time.time(), df)


# ── Sync worker functions (run in executor thread pool) ───────────────────────

def _fetch_worker(symbol: str):
    """Synchronous fetch — runs in thread pool."""
    from data_ingestion import fetch_ohlcv
    return fetch_ohlcv(symbol)


def _features_worker(df):
    """Synchronous feature computation — runs in thread pool."""
    from feature_engine import compute_features
    return compute_features(df)


def _regime_signals_worker(df, symbol: str):
    """Synchronous regime classification and signal generation."""
    from regime import classify_regime
    from strategy_engine import generate_signals
    regime, hurst = classify_regime(df)
    signals = generate_signals(df, regime)
    return regime, hurst, signals


# ── Async Pipeline (single symbol) ────────────────────────────────────────────

async def run_pipeline_async(symbol: str, executor: Optional[ThreadPoolExecutor] = None) -> Optional[dict]:
    """
    Runs the full data → features → regime → signals pipeline asynchronously.

    Args:
        symbol   (str): Ticker symbol (e.g. "AAPL", "NSE:RELIANCE-EQ")
        executor (ThreadPoolExecutor, optional): Shared pool for multi-symbol calls.

    Returns:
        dict with keys: symbol, df, regime, hurst, signals, latency_ms
        Returns None if data fetch or feature computation fails.
    """
    start = time.time()
    loop  = asyncio.get_event_loop()
    own_executor = executor is None
    if own_executor:
        executor = ThreadPoolExecutor(max_workers=4)

    try:
        # ── Step 1: Check feature cache ───────────────────────────────────────
        df_features = _get_cached_features(symbol)

        if df_features is None:
            # ── Step 2: Fetch OHLCV (async, thread pool) ──────────────────────
            logger.info(f"[AsyncEngine] Fetching {symbol}...")
            df_raw = await loop.run_in_executor(executor, _fetch_worker, symbol)

            if df_raw is None or len(df_raw) == 0:
                logger.error(f"[AsyncEngine] Data fetch failed for {symbol}")
                return None

            # ── Step 3: Compute features (async, thread pool) ─────────────────
            logger.info(f"[AsyncEngine] Computing features for {symbol}...")
            df_features = await loop.run_in_executor(executor, _features_worker, df_raw)

            if df_features is None or len(df_features) == 0:
                logger.error(f"[AsyncEngine] Feature computation failed for {symbol}")
                return None

            _store_cached_features(symbol, df_features)

        # ── Step 4: Regime detection + signal generation (fast, inline) ───────
        regime, hurst, signals = await loop.run_in_executor(
            executor, _regime_signals_worker, df_features, symbol
        )

        latency_ms = int((time.time() - start) * 1000)
        logger.info(f"[AsyncEngine] {symbol} pipeline complete in {latency_ms}ms | Regime: {regime}")

        return {
            "symbol":     symbol,
            "df":         df_features,
            "regime":     regime,
            "hurst":      hurst,
            "signals":    signals,
            "latency_ms": latency_ms,
        }

    except Exception as e:
        logger.error(f"[AsyncEngine] Pipeline error for {symbol}: {e}")
        return None

    finally:
        if own_executor:
            executor.shutdown(wait=False)


# ── Async Pipeline (multi-symbol parallel) ────────────────────────────────────

async def run_pipeline_multi(symbols: list) -> dict:
    """
    Runs the full pipeline for multiple symbols simultaneously.
    All symbols execute in parallel — total time ≈ slowest single symbol.

    Args:
        symbols (list): List of ticker symbols

    Returns:
        dict: {symbol -> result_dict | None}
    """
    # Shared thread pool across all symbols to avoid over-subscription
    with ThreadPoolExecutor(max_workers=min(len(symbols) * 2, 16)) as shared_executor:
        tasks   = [run_pipeline_async(sym, executor=shared_executor) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    return {sym: res for sym, res in zip(symbols, results)}


# ── Convenience sync wrapper ───────────────────────────────────────────────────

def run_pipeline(symbol: str) -> Optional[dict]:
    """
    Synchronous convenience wrapper around run_pipeline_async.
    Use this when you don't have an existing event loop.

    Args:
        symbol (str): Ticker symbol

    Returns:
        dict result or None
    """
    return asyncio.run(run_pipeline_async(symbol))
