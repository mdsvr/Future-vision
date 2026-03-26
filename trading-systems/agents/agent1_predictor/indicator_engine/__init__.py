"""
indicator_engine — Technical Indicator Library Interface
=========================================================
Re-exports all indicator functions from the flat-level indicators.py
to provide the modular structure described in the architecture doc.
"""
from indicators import (
    ema, rsi, macd, bollinger_bands, stochastic_rsi,
    atr, obv, obv_slope, vwap,
    hurst_exponent, classify_regime as classify_regime_from_h,
    bollinger_signal, ema_trend_signal, rsi_signal,
    stoch_rsi_signal, confidence_score,
)

__all__ = [
    "ema", "rsi", "macd", "bollinger_bands", "stochastic_rsi",
    "atr", "obv", "obv_slope", "vwap",
    "hurst_exponent", "classify_regime_from_h",
    "bollinger_signal", "ema_trend_signal", "rsi_signal",
    "stoch_rsi_signal", "confidence_score",
]
