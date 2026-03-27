"""
strategy_engine.py  —  Trading Signal Generator
=================================================
Translates technical indicators into simple trading signals: +1, -1, or 0.

SIGNAL VALUES:
  +1 = Bullish  (buy pressure / upward movement likely)
  -1 = Bearish  (sell pressure / downward movement likely)
   0 = Neutral  (no clear signal from this indicator)

FIVE STRATEGIES (upgraded from 3):
  1. Trend        — EMA alignment (long-term direction)
  2. Momentum     — MACD + RSI crossover combo (speed of move)
  3. Mean Reversion — Bollinger Band breakout (overextended price)
  4. Volume       — OBV slope (is smart money buying or selling?)
  5. Stoch RSI    — Stochastic RSI extremes (sensitive reversal detector)

MORE SIGNALS = MORE EVIDENCE.
When all 5 agree → confidence score rises significantly (>70%).
When they conflict → confidence stays low (agent holds).

Used by: main.py → signals dict passed to confidence.py
"""

import pandas as pd
import json
import os

# ── Load config ────────────────────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
def _load_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            _raw = json.load(f)
            return _raw.get("indicators", {}), _raw.get("risk", {})
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to load config: {e}")
        return {}, {}

_cfg, _risk = _load_config()


def generate_signals(df: pd.DataFrame, regime: str = None) -> dict:
    """
    Generates 5 trading signals from the latest candle's computed indicators.

    Args:
        df     (DataFrame): Output of feature_engine.compute_features()
        regime (str):       Market regime — accepted for compatibility, not used here

    Returns:
        dict: 5 signal values, e.g.:
              {"trend": 1, "momentum": 0.6, "mean_reversion": 0,
               "volume": 1, "stoch_rsi": -1}
    """
    if df.empty or len(df) == 0:
        return {}
    
    latest = df.iloc[-1]   # Only need the most recent candle
    signals = {}

    # ── Signal 1: TREND ───────────────────────────────────────────────────────
    # Checks EMA 50 vs EMA 200 alignment (are short-term and long-term trends same?)
    # Best used in trending markets.
    close   = latest.get('close')
    ema_50  = latest.get('ema_50')
    ema_200 = latest.get('ema_200')

    if None in (close, ema_50, ema_200) or pd.isna(close) or pd.isna(ema_50) or pd.isna(ema_200):
        signals['trend'] = 0
    else:
        close, ema_50, ema_200 = float(close), float(ema_50), float(ema_200)
        if close > ema_50 and ema_50 > ema_200:
            signals['trend'] = 1    # Perfect bull alignment: price > EMA50 > EMA200
        elif close < ema_50 and ema_50 < ema_200:
            signals['trend'] = -1   # Perfect bear alignment: price < EMA50 < EMA200
        else:
            signals['trend'] = 0    # EMAs crossing or mixed — no clear trend

    # ── Signal 2: MOMENTUM ────────────────────────────────────────────────────
    # Combines MACD crossover (60%) and RSI level (40%).
    # MACD measures speed/direction of trend; RSI measures overbought/oversold.
    rsi        = latest.get('rsi')
    macd       = latest.get('macd')
    macd_sig   = latest.get('macd_signal')

    if None in (rsi, macd, macd_sig) or pd.isna(rsi) or pd.isna(macd) or pd.isna(macd_sig):
        signals['momentum'] = 0
    else:
        # RSI component: graded signal based on distance from neutral (50)
        if rsi > _cfg.get("rsi_upper", 70):
            rsi_sig = -1                              
        elif rsi < _cfg.get("rsi_lower", 30):
            rsi_sig = 1                               
        else:
            rsi_sig = round((rsi - 50) / -50, 2)     
            rsi_sig = max(-0.5, min(0.5, rsi_sig))   

        macd_diff  = macd - macd_sig
        denom      = abs(macd_sig) + abs(macd) + 1e-9
        macd_strength = macd_diff / denom              
        macd_strength = max(-1.0, min(1.0, macd_strength * 2))  

        signals['momentum'] = float(round(0.6 * macd_strength + 0.4 * rsi_sig, 2))

    # ── Signal 3: MEAN REVERSION (Bollinger Bands) ────────────────────────────
    # UPGRADED from a flat 2% EMA gap to Bollinger Band breakout detection.
    # Bollinger Bands dynamically adjust to volatility — much more accurate.
    #
    # How it works:
    #   Price > upper band → price is statistically overextended → expect FALL → -1
    #   Price < lower band → price is statistically underextended  → expect RISE → +1
    #   Price inside bands → within normal statistical range → no signal → 0
    bb_upper = latest.get('bb_upper', None)
    bb_lower = latest.get('bb_lower', None)

    if bb_upper is not None and bb_lower is not None:
        if close > bb_upper:
            signals['mean_reversion'] = -1   # Above upper band = overextended (sell)
        elif close < bb_lower:
            signals['mean_reversion'] = 1    # Below lower band = oversold (buy)
        else:
            signals['mean_reversion'] = 0    # Inside bands = normal range
    else:
        signals['mean_reversion'] = 0   # Fallback if BB not available

    # ── Signal 4: VOLUME (OBV Slope) ──────────────────────────────────────────
    # NEW SIGNAL — OBV was previously calculated but never used!
    #
    # OBV slope tells us if institutional money is flowing IN or OUT.
    # Smart money moves quietly through volume — this catches it:
    #   Positive OBV slope (OBV rising) = buyers accumulating → +1 bullish
    #   Negative OBV slope (OBV falling) = sellers distributing → -1 bearish
    #   Flat OBV = no conviction from volume → 0 neutral
    obv_slope = latest.get('obv_slope', None)

    if obv_slope is not None:
        if obv_slope > 0:
            signals['volume'] = 1    # Volume flowing in = buyers in control
        elif obv_slope < 0:
            signals['volume'] = -1   # Volume flowing out = sellers in control
        else:
            signals['volume'] = 0    # Neutral volume
    else:
        signals['volume'] = 0

    # ── Signal 5: STOCHASTIC RSI ──────────────────────────────────────────────
    # NEW SIGNAL — More sensitive momentum indicator than plain RSI.
    # Applies the RSI formula TO RSI values, oscillating 0.0 to 1.0.
    #
    # StochRSI > 0.8 → extremely overbought → likely to reverse down → -1
    # StochRSI < 0.2 → extremely oversold  → likely to reverse up   → +1
    # StochRSI 0.2–0.8 → neutral zone → 0
    stoch_rsi = latest.get('stoch_rsi', None)

    if stoch_rsi is not None:
        if stoch_rsi > 0.8:
            signals['stoch_rsi'] = -1   # Extremely overbought
        elif stoch_rsi < 0.2:
            signals['stoch_rsi'] = 1    # Extremely oversold
        else:
            signals['stoch_rsi'] = 0    # Neutral
    else:
        signals['stoch_rsi'] = 0

    return signals