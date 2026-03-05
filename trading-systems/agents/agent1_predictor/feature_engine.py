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
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(_CONFIG_PATH, "r") as f:
    _cfg = json.load(f)["indicators"]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enriches a raw OHLCV DataFrame with all technical indicators.

    Args:
        df (DataFrame): Raw price data with columns: open, high, low, close, volume

    Returns:
        DataFrame: Same data plus indicator columns. First N rows (warm-up period) dropped.
    """
    df = df.copy()

    # ── TREND INDICATORS ──────────────────────────────────────────────────────

    # EMA 200 — Long-term trend (Golden/Death Cross framework)
    # Price above EMA200 = overall bullish market; below = bearish
    df['ema_200'] = df['close'].ewm(span=_cfg["ema_slow"]).mean()

    # EMA 50 — Medium-term trend
    # EMA50 crossing EMA200 upward = "Golden Cross" (strong buy signal)
    # EMA50 crossing EMA200 downward = "Death Cross" (strong sell signal)
    df['ema_50']  = df['close'].ewm(span=_cfg["ema_fast"]).mean()

    # ── MOMENTUM INDICATORS ───────────────────────────────────────────────────

    # RSI — Relative Strength Index (0–100)
    # >70: Overbought (likely to pull back)   <30: Oversold (likely to bounce)
    delta = df['close'].diff()
    gain  = delta.clip(lower=0).rolling(_cfg["rsi_period"]).mean()
    loss  = (-delta.clip(upper=0)).rolling(_cfg["rsi_period"]).mean()
    rs    = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic RSI — applies RSI formula TO the RSI values
    # More sensitive than plain RSI — catches reversals before they appear in raw RSI
    # StochRSI near 1.0 = extremely overbought; near 0.0 = extremely oversold
    rsi_min = df['rsi'].rolling(_cfg["stoch_rsi_period"]).min()
    rsi_max = df['rsi'].rolling(_cfg["stoch_rsi_period"]).max()
    rsi_range = rsi_max - rsi_min
    df['stoch_rsi'] = (df['rsi'] - rsi_min) / (rsi_range + 1e-9)

    # MACD — Moving Average Convergence Divergence
    # MACD line crossing above signal = bullish; below = bearish
    ema_fast         = df['close'].ewm(span=_cfg["macd_fast"]).mean()
    ema_slow         = df['close'].ewm(span=_cfg["macd_slow"]).mean()
    df['macd']        = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=_cfg["macd_signal"]).mean()

    # ── MEAN REVERSION — BOLLINGER BANDS ─────────────────────────────────────
    # Bollinger Bands create a volatility envelope around price.
    # Upper Band = SMA + (2 × standard deviation of price)
    # Lower Band = SMA − (2 × standard deviation of price)
    #
    # Price ABOVE upper band → overextended (likely to fall back) →  SELL signal
    # Price BELOW lower band → oversold (likely to bounce up)    →  BUY signal
    # Price inside bands     → normal range, no reversal signal
    #
    # Bollinger Width (how wide the bands are) measures volatility compression.
    # A very narrow "squeeze" often precedes a big breakout move.
    bb_period = _cfg["bollinger_period"]
    bb_std    = _cfg["bollinger_std"]
    bb_sma    = df['close'].rolling(bb_period).mean()
    bb_sigma  = df['close'].rolling(bb_period).std()
    df['bb_upper'] = bb_sma + bb_std * bb_sigma
    df['bb_lower'] = bb_sma - bb_std * bb_sigma
    df['bb_mid']   = bb_sma
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (bb_sma + 1e-9)  # Normalized width

    # ── VOLUME INDICATORS ─────────────────────────────────────────────────────

    # OBV — On-Balance Volume
    # Cumulative volume flow: +volume when price goes up, -volume when price goes down
    # Rising OBV + rising price = strong uptrend (institutional buyers accumulating)
    # Falling OBV + rising price = warning sign (distribution — smart money selling)
    df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

    # OBV Slope — is volume flow accelerating up or down over last N candles?
    # Used in strategy_engine to confirm trend with volume
    slope_period = _cfg.get("obv_slope_period", 5)
    df['obv_slope'] = df['obv'].diff(slope_period)  # Positive = rising OBV, Negative = falling

    # Volume Spike — sudden surge above average signals institutional interest
    df['volume_avg']   = df['volume'].rolling(_cfg["obv_volume_avg_period"]).mean()
    df['volume_spike'] = df['volume'] > _cfg["obv_volume_spike_multiplier"] * df['volume_avg']

    # ── VOLATILITY — ATR ──────────────────────────────────────────────────────

    # ATR — Average True Range: average size of price swings per candle
    # High ATR → volatile → set wider stops ; Low ATR → quiet → tighter stops
    tr1 = df['high'] - df['low']
    tr2 = abs(df['high'] - df['close'].shift())
    tr3 = abs(df['low']  - df['close'].shift())
    df['tr']  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(_cfg["atr_period"]).mean()

    # ── VOLUME WEIGHTED AVERAGE PRICE (VWAP) ─────────────────────────────────
    # VWAP = best intraday "fair value" benchmark used by institutional traders.
    # Price above VWAP = buyers in control (bullish bias)
    # Price below VWAP = sellers in control (bearish bias)
    #
    # For intraday candles: cumulative sum of (typical price × volume) / cumulative volume
    # Typical price = (high + low + close) / 3
    #
    # NOTE: For INDEX symbols (VIX, NIFTY50 etc.), volume is always 0.
    # To avoid NaN from 0/0, we fall back to using the close price as VWAP.
    tp = (df['high'] + df['low'] + df['close']) / 3   # Typical price per candle
    cumvol = df['volume'].cumsum()
    if cumvol.iloc[-1] == 0:
        # Zero-volume index: VWAP is meaningless — use close as a proxy
        df['vwap'] = df['close']
    else:
        df['vwap'] = (tp * df['volume']).cumsum() / cumvol.replace(0, float('nan'))
        df['vwap'] = df['vwap'].ffill()  # Forward-fill any gaps from partial zero-volume candles

    # Drop warm-up rows using only the core trend indicators as the NaN gate.
    # We do NOT use df.dropna() on all columns because:
    #   - Index symbols have volume=0 → OBV/volume_spike cols may stay NaN all rows
    #   - We only need EMA, RSI, MACD, BB, ATR to be ready before we can analyse
    core_cols = ['ema_200', 'ema_50', 'rsi', 'macd', 'macd_signal',
                 'bb_upper', 'bb_lower', 'atr']
    df = df.dropna(subset=core_cols)

    # Fill any remaining NaN in optional cols with safe neutral values
    df['stoch_rsi']    = df['stoch_rsi'].fillna(0.5)    # Neutral StochRSI
    df['obv_slope']    = df['obv_slope'].fillna(0)       # Flat OBV slope
    df['volume_avg']   = df['volume_avg'].fillna(0)
    df['volume_spike'] = df['volume_spike'].fillna(False)
    df['vwap']         = df['vwap'].fillna(df['close'])  # VWAP fallback to close

    return df