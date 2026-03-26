"""
regime.py  —  Market Regime Detector
=====================================
Figures out WHAT TYPE of market we're in right now.

There are 3 types of markets:
  1. TRENDING   — Price is moving consistently in one direction (up or down)
  2. MEAN_REVERTING — Price keeps bouncing back to a central level (choppy)
  3. RANDOM     — No clear pattern (noise, sideways drift)

WHY does this matter?
  - In a TRENDING market  → Follow the trend (BUY if going up, SELL if going down)
  - In a MEAN REVERTING   → Fade the move (price will come back, so do the opposite)
  - In a RANDOM market    → Don't trade. The AI lowers its confidence.

HOW we detect this: The Hurst Exponent
  The Hurst Exponent (H) is a number between 0 and 1 calculated from price history.
  - H > 0.55  →  Trending    (price has 'memory', keeps moving same direction)
  - H < 0.45  →  Mean-Reverting (price 'snaps back' like a rubber band)
  - H ≈ 0.5   →  Random walk   (completely unpredictable, like a coin flip)

Used by: main.py → passed to confidence.py and llm_reasoner.py
"""

import numpy as np
import pandas as pd


def calculate_hurst_exponent(series, max_lag=20):
    """
    Estimates the Hurst Exponent (H) from a price series.
    
    Method: Variance of differenced returns across multiple lag windows.
    We fit a log-log regression line — the slope tells us H.
    
    Args:
        series   (array): Closing prices, e.g. [100.5, 101.2, 99.8, ...]
        max_lag  (int):   How many lag steps to check. More = slower but more accurate.
    
    Returns:
        float: Hurst exponent H (between 0 and 1), or 0.5 if computation fails.
    
    Edge cases handled:
        - Constant/flat series (e.g. VIX warm-up rows) → all tau=0 → log(0)=error → returns 0.5
        - Too few rows → falls back to max_lag=min(len,20) or returns 0.5
    """
    try:
        lags = range(2, min(max_lag, len(series) // 2))
        if len(list(lags)) < 3:
            return 0.5   # Not enough data — call it random

        # For each lag distance, calculate the standard deviation of price differences
        # This measures how much prices diverge as we look further apart in time
        tau = [
            np.sqrt(np.std(series[lag:] - series[:-lag]))
            for lag in lags
        ]

        # Guard: if all tau values are zero (perfectly flat series), log(0) is undefined
        tau = np.array(tau)
        valid = tau > 0
        if valid.sum() < 3:
            return 0.5   # Flat/constant data — treat as random

        lags_arr = np.array(list(lags))[valid]
        tau_arr  = tau[valid]

        # Fit a straight line on a log-log scale
        # The slope of this line IS the Hurst Exponent
        poly = np.polyfit(np.log(lags_arr), np.log(tau_arr), 1)
        h = poly[0] * 2.0

        # Sanity check: H should be between 0 and 1
        if not np.isfinite(h) or h < 0 or h > 1:
            return 0.5   # Bad result — default to random

        return h

    except Exception:
        return 0.5   # Any unexpected error → call it random


def classify_regime(df):
    """
    Classifies the current market environment into one of 4 regimes.

    Regime priority order:
      1. VOLATILE     — ATR spike > 2× rolling mean (overrides Hurst)
      2. TRENDING     — Hurst > 0.55
      3. MEAN_REVERTING — Hurst < 0.45
      4. RANDOM       — 0.45 ≤ Hurst ≤ 0.55

    Args:
        df (DataFrame): OHLCV data with 'close' column.
                        If 'atr' column is present, it is used for volatile detection.

    Returns:
        tuple: (regime_name, hurst_value)
            regime_name: "trending" | "mean_reverting" | "volatile" | "random"
            hurst_value: the raw H value (e.g. 0.62)

    Example:
        regime, hurst = classify_regime(df)
        # regime = "trending", hurst = 0.62
    """
    close_series = df['close'].values
    hurst = calculate_hurst_exponent(close_series)

    # ── Hurst-based primary classification ────────────────────────────────────
    if hurst > 0.55:
        regime = "trending"
    elif hurst < 0.45:
        regime = "mean_reverting"
    else:
        regime = "random"

    # ── Volatile override via ATR z-score ─────────────────────────────────────
    # If the latest ATR is > 2× its 50-period rolling mean, the market is in a
    # spike/crisis state. This overrides the Hurst classification entirely because
    # technical mean reversion or trend signals become unreliable in spike conditions.
    if 'atr' in df.columns:
        atr_series   = df['atr'].dropna()
        if len(atr_series) >= 10:
            atr_mean_50  = atr_series.rolling(min(50, len(atr_series))).mean().iloc[-1]
            atr_current  = atr_series.iloc[-1]
            if atr_mean_50 > 0 and atr_current > 2.0 * atr_mean_50:
                regime = "volatile"

    return regime, round(hurst, 3)