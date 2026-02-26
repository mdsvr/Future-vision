import pandas as pd
import numpy as np
import json
import os

# Load indicator periods and thresholds from central config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)["indicators"]

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enriches raw OHLCV data with technical indicators.
    Uses vectorised pandas operations for performance.
    """
    df = df.copy()

    # --- Trend Indicators ---
    # EMA (Exponential Moving Average) captures multi-horizon trends
    df['ema_200'] = df['close'].ewm(span=config["ema_slow"]).mean()
    df['ema_50'] = df['close'].ewm(span=config["ema_fast"]).mean()

    # --- Momentum Indicators ---
    # RSI (Relative Strength Index) detects Overbought (>70) and Oversold (<30)
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(config["rsi_period"]).mean()
    loss = (-delta.clip(upper=0)).rolling(config["rsi_period"]).mean()
    rs = gain / (loss + 1e-9) # Add epsilon to prevent div-by-zero
    df['rsi'] = 100 - (100 / (1 + rs))

    # MACD (Moving Average Convergence Divergence) signals momentum shifts
    ema12 = df['close'].ewm(span=config["macd_fast"]).mean()
    ema26 = df['close'].ewm(span=config["macd_slow"]).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=config["macd_signal"]).mean()
    
    # --- Volume Indicators ---
    # OBV (On-Balance Volume) tracks cumulative flow of volume based on price direction
    df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
    
    # Volume Spike Detection helps confirm breakouts
    df['volume_avg'] = df['volume'].rolling(config["obv_volume_avg_period"]).mean()
    df['volume_spike'] = df['volume'] > config["obv_volume_spike_multiplier"] * df['volume_avg']
    
    # --- Volatility Indicators ---
    # ATR (Average True Range) measures market volatility; critical for stop-loss distance
    tr1 = df['high'] - df['low']
    tr2 = abs(df['high'] - df['close'].shift())
    tr3 = abs(df['low'] - df['close'].shift())
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(config["atr_period"]).mean()

    # Drop the first N rows where indicators are still 'warming up'
    return df.dropna()