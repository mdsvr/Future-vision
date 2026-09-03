"""
feature_engine.py  —  Technical Indicator Calculator
======================================================
Takes raw OHLCV (Open, High, Low, Close, Volume) price data
and adds a set of technical indicators used by traders worldwide.

INDICATORS ADDED:
  ┌──────────────────────┬────────────────────────────────────────────────────┐
  │ Indicator            │ What it tells us                                   │
  ├──────────────────────┼────────────────────────────────────────────────────┤
  │ EMA 200              │ Long-term trend (above = bullish, below = bear)    │
  │ EMA 50               │ Medium-term trend                                  │
  │ RSI (14)             │ Momentum: >70 = overbought, <30 = oversold         │
  │ Stochastic RSI       │ More sensitive RSI — catches reversals earlier     │
  │ MACD                 │ Momentum shift signal                              │
  │ MACD Signal          │ Smoothed MACD for crossover detection              │
  │ Bollinger Upper/Lower│ Price channel — breakout = momentum signal         │
  │ Bollinger Width      │ Squeeze = volatility compression before a move     │
  │ OBV                  │ Volume flow (rising = buyers, falling = sellers)   │
  │ Volume Spike         │ Unusual volume = potential breakout                │
  │ ATR (14)             │ Volatility — used for stop-loss distance           │
  │ VWAP                 │ Intraday fair value line (best entry benchmark)    │
  └──────────────────────┴────────────────────────────────────────────────────┘

Config values (periods) come from config.json → "indicators" section.
Used by: main.py → df is passed to strategy_engine.py after this step.
"""

import pandas as pd
import numpy as np
import json
import os

# ── Load indicator periods from config.json ────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
def _load_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f).get("indicators", {})
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to load indicator config: {e}")
        return {}

_cfg = _load_config()


import asyncio
from concurrent.futures import ThreadPoolExecutor

# Make sure we use absolute import or explicit relative import to grab pure functions
# Assuming indicators.py is side-by-side with feature_engine.py
from . import indicators

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Synchronous wrapper for compute_features_async.
    Used by components that still rely on sequential/blocking patterns (like safe mode).
    Will initialize a ThreadPoolExecutor implicitly.

    Callers already inside an event loop should await compute_features_async()
    directly — asyncio.run() cannot re-enter a running loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(compute_features_async(df))

    # ponytail: already in a loop — hand the coroutine to a worker thread so this
    # stays a working sync call. It blocks the loop; await the async version instead.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, compute_features_async(df)).result()

async def compute_features_async(df: pd.DataFrame, executor: ThreadPoolExecutor = None) -> pd.DataFrame:
    """
    Enriches a raw OHLCV DataFrame with all technical indicators asynchronously.
    Dispatches disjoint groups of indicators to thread pool workers.

    Args:
        df (DataFrame): Raw price data with columns: open, high, low, close, volume
        executor: Optional shared ThreadPoolExecutor.

    Returns:
        DataFrame: Same data plus indicator columns. First N rows (warm-up period) dropped.
    """
    df = df.copy()

    def calc_trend():
        ema200 = indicators.ema(df['close'], _cfg.get("ema_slow", 200))
        ema50  = indicators.ema(df['close'], _cfg.get("ema_fast", 50))
        return {'ema_200': ema200, 'ema_50': ema50}

    def calc_momentum():
        rsi_s = indicators.rsi(df['close'], _cfg.get("rsi_period", 14))
        # StochRSI needs the raw RSI passed, but since it's a pure function wrapper in indicators.py,
        # it calls rsi() again internally (or we handle it directly if we want)
        stoch_rsi_s = indicators.stochastic_rsi(df['close'], _cfg.get("stoch_rsi_period", 14))
        macd_d = indicators.macd(df['close'], _cfg.get("macd_fast", 12), _cfg.get("macd_slow", 26), _cfg.get("macd_signal", 9))
        return {
            'rsi': rsi_s,
            'stoch_rsi': stoch_rsi_s,
            'macd': macd_d['macd'],
            'macd_signal': macd_d['signal']
        }

    def calc_volatility():
        bb_d = indicators.bollinger_bands(df['close'], _cfg.get("bollinger_period", 20), _cfg.get("bollinger_std", 2))
        atr_s = indicators.atr(df['high'], df['low'], df['close'], _cfg.get("atr_period", 14))
        return {
            'bb_upper': bb_d['upper'], 'bb_lower': bb_d['lower'],
            'bb_mid': bb_d['mid'], 'bb_width': bb_d['width'],
            'atr': atr_s
        }

    def calc_volume():
        obv_s = indicators.obv(df['close'], df['volume'])
        obv_slope_s = indicators.obv_slope(obv_s, _cfg.get("obv_slope_period", 5))
        
        vol_avg = df['volume'].rolling(_cfg.get("obv_volume_avg_period", 20)).mean()
        vol_spike = df['volume'] > (_cfg.get("obv_volume_spike_multiplier", 1.5) * vol_avg)
        
        return {'obv': obv_s, 'obv_slope': obv_slope_s, 'volume_avg': vol_avg, 'volume_spike': vol_spike}

    def calc_vwap():
        if df.empty or df['volume'].size == 0:
            return {'vwap': df.get('close', pd.Series(dtype=float))}
            
        cumvol_last = df['volume'].cumsum().iloc[-1]
        if cumvol_last == 0:
            return {'vwap': df['close']}
            
        return {'vwap': indicators.vwap(df['high'], df['low'], df['close'], df['volume'])}

    # Get event loop to dispatch to executor
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Launch in parallel
    task_results = await asyncio.gather(
        loop.run_in_executor(executor, calc_trend),
        loop.run_in_executor(executor, calc_momentum),
        loop.run_in_executor(executor, calc_volatility),
        loop.run_in_executor(executor, calc_volume),
        loop.run_in_executor(executor, calc_vwap)
    )

    # Merge results
    for res_dict in task_results:
        for col_name, series in res_dict.items():
            df[col_name] = series

    # Drop warm-up rows
    core_cols = ['ema_200', 'ema_50', 'rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_lower', 'atr']
    df = df.dropna(subset=core_cols)

    # Fill any remaining NaN in optional cols with safe neutral values
    df['stoch_rsi']    = df['stoch_rsi'].fillna(0.5)
    df['obv_slope']    = df['obv_slope'].fillna(0)
    df['volume_avg']   = df['volume_avg'].fillna(0)
    df['volume_spike'] = df['volume_spike'].fillna(False)
    
    if 'vwap' in df:
        df['vwap'] = df['vwap'].fillna(df['close'])
    else:
        df['vwap'] = df['close']

    return df