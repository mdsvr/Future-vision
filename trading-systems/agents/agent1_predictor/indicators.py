"""
indicators.py  —  Standalone Indicator Functions
=================================================
Each function here takes a pandas Series or DataFrame and returns
a computed indicator value or Series. They can be used independently
for testing, research, or custom strategies.

All functions are pure — they don't modify the input data.

AVAILABLE FUNCTIONS:
    ema(series, period)              → Exponential Moving Average series
    rsi(series, period)              → RSI series (0–100)
    macd(series, fast, slow, signal) → dict with macd, signal, histogram
    bollinger_bands(series, period, std_dev) → dict with upper, lower, mid, width
    stochastic_rsi(series, period)   → StochRSI series (0.0–1.0)
    atr(high, low, close, period)    → ATR series
    obv(close, volume)               → OBV cumulative series
    obv_slope(obv_series, n)         → OBV slope over last n candles
    vwap(high, low, close, volume)   → VWAP series
    hurst_exponent(series, max_lag)  → float H value
    classify_regime(h)               → str regime label
    bollinger_signal(close, upper, lower) → int signal (+1, -1, 0)
    confidence_score(signals, regime, atr_pct) → float 0.0–1.0
"""

import math
import numpy as np
import pandas as pd


# ─────────────────────────────────────────────
#  TREND INDICATORS
# ─────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    """
    Exponential Moving Average — gives more weight to recent prices.

    Formula: EMA_t = Price_t × k + EMA_(t-1) × (1-k)
             where k = 2 / (period + 1)

    Args:
        series (pd.Series): Closing prices
        period (int):       Lookback (e.g. 50 or 200)

    Returns:
        pd.Series: EMA values (same length as input)

    Example:
        ema_50 = ema(df['close'], 50)
        print(f"EMA50: {ema_50.iloc[-1]:.2f}")
    """
    return series.ewm(span=period, adjust=False).mean()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Volume Weighted Average Price — the average price weighted by traded volume.
    Best intraday 'fair value' benchmark.

    Formula: VWAP = Σ(typical_price × volume) / Σ(volume)
             typical_price = (high + low + close) / 3

    Args:
        high, low, close (pd.Series): OHLC columns
        volume (pd.Series):            Volume column

    Returns:
        pd.Series: Cumulative VWAP series

    Example:
        df['vwap'] = vwap(df['high'], df['low'], df['close'], df['volume'])
    """
    typical_price = (high + low + close) / 3
    return (typical_price * volume).cumsum() / volume.cumsum()


# ─────────────────────────────────────────────
#  MOMENTUM INDICATORS
# ─────────────────────────────────────────────

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index — measures momentum speed and direction.

    Formula: RSI = 100 - (100 / (1 + RS))
             RS  = Avg Gain / Avg Loss over `period` candles

    Interpretation:
        > 70  → Overbought (likely to fall soon)
        < 30  → Oversold   (likely to bounce soon)
        30–70 → Neutral

    Args:
        series (pd.Series): Closing prices
        period (int):       Lookback period (default 14)

    Returns:
        pd.Series: RSI values (0–100 scale)
    """
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / (loss + 1e-9)     # 1e-9 prevents division by zero
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal_period: int = 9) -> dict:
    """
    MACD — Moving Average Convergence Divergence.
    Measures rate and direction of momentum change.

    Formula:
        MACD Line   = EMA(fast) - EMA(slow)
        Signal Line = EMA(9) of MACD Line
        Histogram   = MACD Line - Signal Line

    Interpretation:
        MACD crosses above Signal → Bullish momentum building
        MACD crosses below Signal → Bearish momentum building
        Histogram positive/growing → Trend strengthening

    Args:
        series        (pd.Series): Closing prices
        fast          (int):       Fast EMA period (default 12)
        slow          (int):       Slow EMA period (default 26)
        signal_period (int):       Signal EMA period (default 9)

    Returns:
        dict with keys: 'macd', 'signal', 'histogram' (all pd.Series)
    """
    ema_fast  = series.ewm(span=fast, adjust=False).mean()
    ema_slow  = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig_line  = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - sig_line
    return {"macd": macd_line, "signal": sig_line, "histogram": histogram}


def stochastic_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Stochastic RSI — applies the Stochastic formula to RSI values.
    More sensitive than plain RSI — catches reversals earlier.

    Formula: StochRSI = (RSI - RSI_min) / (RSI_max - RSI_min)
             over a rolling window of `period`

    Interpretation:
        > 0.8  → Extremely overbought → expect pullback → SELL signal
        < 0.2  → Extremely oversold   → expect bounce  → BUY signal
        0.2–0.8 → Neutral zone

    Args:
        series (pd.Series): Closing prices
        period (int):       Rolling window for min/max RSI (default 14)

    Returns:
        pd.Series: StochRSI values (0.0 to 1.0)
    """
    rsi_vals = rsi(series, period)
    rsi_min  = rsi_vals.rolling(period).min()
    rsi_max  = rsi_vals.rolling(period).max()
    return (rsi_vals - rsi_min) / (rsi_max - rsi_min + 1e-9)


# ─────────────────────────────────────────────
#  VOLATILITY INDICATORS
# ─────────────────────────────────────────────

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average True Range — measures average size of price swings per candle.
    Used to set stop-loss distances and gauge market volatility.

    Formula:
        True Range = max(
            High - Low,                     ← Candle body
            |High - Previous Close|,        ← Gap up scenario
            |Low  - Previous Close|         ← Gap down scenario
        )
        ATR = Rolling Mean of True Range over `period` candles

    Interpretation:
        High ATR → volatile, use wider stop loss
        Low ATR  → quiet, can use tighter stop loss

    Args:
        high, low, close (pd.Series): Price columns
        period (int):                 Rolling average window (default 14)

    Returns:
        pd.Series: ATR values in price units
    """
    tr1 = high - low                             # Simple candle range
    tr2 = (high - close.shift()).abs()           # Gap from prior close to high
    tr3 = (low  - close.shift()).abs()           # Gap from prior close to low
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
    """
    Bollinger Bands — dynamic price channel based on standard deviation.
    Adjusts automatically to market volatility.

    Formula:
        Middle Band = SMA(close, period)
        Upper Band  = Middle + std_dev × σ(close, period)
        Lower Band  = Middle - std_dev × σ(close, period)
        Width       = (Upper - Lower) / Middle   ← Normalized volatility

    Interpretation:
        Price > Upper Band → Statistically overextended → expect FALL   → -1
        Price < Lower Band → Statistically underextended → expect RISE  → +1
        Price inside bands → Normal range, no mean-reversion signal
        Narrow Width (squeeze) → Low volatility, big move coming soon

    Args:
        series  (pd.Series): Closing prices
        period  (int):       SMA and std lookback (default 20)
        std_dev (float):     Standard deviation multiplier (default 2.0)

    Returns:
        dict with keys: 'upper', 'lower', 'mid', 'width' (all pd.Series)
    """
    mid   = series.rolling(period).mean()
    sigma = series.rolling(period).std()
    upper = mid + std_dev * sigma
    lower = mid - std_dev * sigma
    width = (upper - lower) / (mid + 1e-9)
    return {"upper": upper, "lower": lower, "mid": mid, "width": width}


# ─────────────────────────────────────────────
#  VOLUME INDICATORS
# ─────────────────────────────────────────────

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On-Balance Volume — cumulative volume flow indicator.
    Tracks whether big money is buying (accumulating) or selling (distributing).

    Formula:
        OBV_t = OBV_(t-1) + volume   if close > close_(t-1)
        OBV_t = OBV_(t-1) - volume   if close < close_(t-1)
        OBV_t = OBV_(t-1)            if close = close_(t-1)

    Interpretation:
        Rising OBV + Rising Price   → Strong uptrend (confirmed by volume)
        Falling OBV + Rising Price  → Warning: price may reverse (divergence)
        Rising OBV + Falling Price  → Possible bottom forming

    Args:
        close  (pd.Series): Closing prices
        volume (pd.Series): Volume

    Returns:
        pd.Series: Cumulative OBV values
    """
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def obv_slope(obv_series: pd.Series, n: int = 5) -> pd.Series:
    """
    OBV Slope — rate of change of OBV over the last n candles.
    Tells us if volume flow is accelerating in or out.

    Formula: slope_t = OBV_t - OBV_(t-n)

    Interpretation:
        Positive slope → Volume flowing IN  → Buyers accumulating → +1 bullish
        Negative slope → Volume flowing OUT → Sellers distributing → -1 bearish
        Near zero      → Volume flat, no directional conviction

    Args:
        obv_series (pd.Series): Output of obv() function
        n          (int):       Lookback candles for slope (default 5)

    Returns:
        pd.Series: Slope values (positive = bullish volume, negative = bearish)
    """
    return obv_series.diff(n)


# ─────────────────────────────────────────────
#  REGIME DETECTION
# ─────────────────────────────────────────────

def hurst_exponent(series: pd.Series, max_lag: int = 20) -> float:
    """
    Hurst Exponent — classifies the market's statistical behavior.

    Formula:
        For each lag τ from 2 to max_lag:
            τ_std = sqrt( std( price[τ:] - price[:-τ] ) )
        Fit log-log regression: slope of log(τ_std) vs log(τ)
        H = slope × 2

    Interpretation:
        H > 0.55 → TRENDING   (price has memory, keeps going same direction)
        H < 0.45 → MEAN-REVERTING (price snaps back like rubber band)
        H ≈ 0.50 → RANDOM     (coin flip — no predictable pattern)

    Args:
        series  (pd.Series or np.array): Closing prices
        max_lag (int):                   Max lag to compute (default 20)

    Returns:
        float: Hurst exponent H (typically 0.3 to 0.7)
    """
    arr  = np.array(series)
    lags = range(2, max_lag)
    tau  = [np.sqrt(np.std(arr[lag:] - arr[:-lag])) for lag in lags]
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return round(poly[0] * 2.0, 4)


def classify_regime(h: float) -> str:
    """
    Converts a Hurst exponent value into a human-readable regime label.

    Args:
        h (float): Hurst exponent from hurst_exponent()

    Returns:
        str: "trending" | "mean_reverting" | "random"
    """
    if h > 0.55:
        return "trending"
    elif h < 0.45:
        return "mean_reverting"
    return "random"


# ─────────────────────────────────────────────
#  SIGNAL FUNCTIONS
# ─────────────────────────────────────────────

def bollinger_signal(close_val: float, upper_val: float, lower_val: float) -> int:
    """
    Generates a mean-reversion signal from Bollinger Bands.

    Args:
        close_val (float): Current closing price
        upper_val (float): Current upper Bollinger Band
        lower_val (float): Current lower Bollinger Band

    Returns:
        int: +1 (oversold, expect rise), -1 (overbought, expect fall), 0 (neutral)
    """
    if close_val > upper_val:
        return -1   # Price above upper band → overextended → expect fall
    elif close_val < lower_val:
        return 1    # Price below lower band → oversold → expect bounce
    return 0


def ema_trend_signal(close_val: float, ema50_val: float, ema200_val: float) -> int:
    """
    Generates a trend signal from EMA 50 vs EMA 200 alignment.

    Args:
        close_val  (float): Current price
        ema50_val  (float): EMA 50 value
        ema200_val (float): EMA 200 value

    Returns:
        int: +1 (bullish alignment), -1 (bearish alignment), 0 (mixed)
    """
    if close_val > ema50_val > ema200_val:
        return 1    # Golden alignment: price > EMA50 > EMA200 → bullish
    elif close_val < ema50_val < ema200_val:
        return -1   # Death alignment: price < EMA50 < EMA200 → bearish
    return 0


def rsi_signal(rsi_val: float, overbought: float = 70, oversold: float = 30) -> int:
    """
    Generates a momentum signal from RSI value.

    Args:
        rsi_val     (float): Current RSI value
        overbought  (float): Threshold for overbought (default 70)
        oversold    (float): Threshold for oversold (default 30)

    Returns:
        int: -1 (overbought), +1 (oversold), 0 (neutral)
    """
    if rsi_val > overbought:
        return -1   # Overbought → likely pullback → bearish
    elif rsi_val < oversold:
        return 1    # Oversold → likely bounce → bullish
    return 0


def stoch_rsi_signal(stoch_val: float, high_thresh: float = 0.8, low_thresh: float = 0.2) -> int:
    """
    Generates a signal from Stochastic RSI value.

    Args:
        stoch_val   (float): Current StochRSI value (0.0–1.0)
        high_thresh (float): Overbought threshold (default 0.8)
        low_thresh  (float): Oversold threshold (default 0.2)

    Returns:
        int: -1 (overbought), +1 (oversold), 0 (neutral)
    """
    if stoch_val > high_thresh:
        return -1
    elif stoch_val < low_thresh:
        return 1
    return 0


# ─────────────────────────────────────────────
#  CONFIDENCE SCORER
# ─────────────────────────────────────────────

def confidence_score(signals: dict, regime: str, atr_percentile: float) -> float:
    """
    Computes a regime-weighted conviction score from the 5 trading signals.

    Weights:
        trending       → trend 40%, momentum 25%, mean_rev 10%, volume 15%, stoch_rsi 10%
        mean_reverting → trend 15%, momentum 20%, mean_rev 35%, volume 15%, stoch_rsi 15%
        random         → all equal at 20%

    Args:
        signals        (dict):  5 signal values {trend, momentum, mean_reversion,
                                volume, stoch_rsi} each in range [-1, +1]
        regime         (str):   "trending" | "mean_reverting" | "random"
        atr_percentile (float): 0.0–1.0, where current volatility sits historically

    Returns:
        float: Conviction score 0.0–1.0 (shown as 0%–100%)
    """
    WEIGHTS = {
        "trending":       {"trend": 0.40, "momentum": 0.25, "mean_reversion": 0.10, "volume": 0.15, "stoch_rsi": 0.10},
        "mean_reverting": {"trend": 0.15, "momentum": 0.20, "mean_reversion": 0.35, "volume": 0.15, "stoch_rsi": 0.15},
        "random":         {"trend": 0.20, "momentum": 0.20, "mean_reversion": 0.20, "volume": 0.20, "stoch_rsi": 0.20},
    }
    weights = WEIGHTS.get(regime, WEIGHTS["random"])

    weighted_vals = [signals.get(k, 0) * w for k, w in weights.items()]
    total_abs     = sum(abs(v) for v in weighted_vals)
    consensus     = abs(sum(weighted_vals)) / (total_abs + 1e-9)

    vals      = list(signals.values())
    mean_val  = sum(vals) / len(vals)
    variance  = sum((v - mean_val) ** 2 for v in vals) / (len(vals) + 1e-9)
    dispersion_penalty = 1 - min(variance * 0.5, 0.8)

    regime_factor   = {"trending": 1.10, "mean_reverting": 1.05, "random": 0.72}.get(regime, 0.72)
    vol_factor      = 0.65 if atr_percentile > 0.95 else 0.85 if atr_percentile > 0.80 else 0.75 if atr_percentile < 0.05 else 1.0
    alignment_bonus = 1.08 if regime == "trending" and signals.get("trend", 0) != 0 else 1.0

    raw = consensus * dispersion_penalty * regime_factor * vol_factor * alignment_bonus
    return round(min(1 / (1 + math.exp(-5 * (raw - 0.5))), 1.0), 3)
