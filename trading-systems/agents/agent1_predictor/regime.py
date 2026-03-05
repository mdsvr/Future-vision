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
    Classifies the current market environment into one of 3 regimes.
    
    Args:
        df (DataFrame): OHLCV data with at least a 'close' column.
    
    Returns:
        tuple: (regime_name, hurst_value)
            regime_name: "trending" | "mean_reverting" | "random"
            hurst_value: the raw H value (e.g. 0.62)
    
    Example:
        regime, hurst = classify_regime(df)
        # regime = "trending", hurst = 0.62
    """
    close_series = df['close'].values
    hurst = calculate_hurst_exponent(close_series)

    # Standard quant thresholds for regime classification
    if hurst > 0.55:
        regime = "trending"       # Strong directional move
    elif hurst < 0.45:
        regime = "mean_reverting" # Price oscillates around a mean
    else:
        regime = "random"         # No clear structure — proceed with caution

    return regime, round(hurst, 3)