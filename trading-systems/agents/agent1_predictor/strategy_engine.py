import json
import os

# Load technical constants from config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)["indicators"]

def generate_signals(df, regime):
    """
    Translates technical data points into directional trading signals.
    :param df: Cleaned DataFrame with indicators.
    :param regime: Detected market state (Trending, Mean Reverting, etc.)
    :return: Dictionary of signals [-1, 0, 1] for different strategies.
    """
    latest = df.iloc[-1]

    # Convert to scalar floats for simple comparison
    close = float(latest['close'])
    ema200 = float(latest['ema_200'])
    macd = float(latest['macd'])
    macd_signal = float(latest['macd_signal'])
    rsi = float(latest['rsi'])

    signals = {}

    # --- Strategy A: Trend Following ---
    # Basic rule: Is price above or below the long-term baseline?
    signals['trend'] = 1 if close > ema200 else -1

    # --- Strategy B: Momentum ---
    # We combine MACD crossover with RSI being in the 'active' half of the range.
    macd_sig = 1 if macd > macd_signal else -1
    rsi_sig = 1 if rsi > 50 else -1
    signals['momentum'] = (macd_sig + rsi_sig) / 2

    # --- Strategy C: Mean Reversion ---
    # Looking for 'rubber band' stretches using RSI bounds from config.
    if rsi < config["rsi_lower"]:
        signals['mean_reversion'] = 1  # Oversold: Buy the dip
    elif rsi > config["rsi_upper"]:
        signals['mean_reversion'] = -1 # Overbought: Sell the peak
    else:
        signals['mean_reversion'] = 0

    return signals