"""
confidence.py  —  Trade Conviction Scorer
==========================================
Answers the question: "How SURE is the AI about this trade?"

The output is a number from 0.0 to 1.0 (shown as 0% to 100%).

  Below 0.55 (55%) → Agent says HOLD (not confident enough to act)
  Above 0.55 (55%) → Agent can consider BUY or SELL

UPGRADE: REGIME-WEIGHTED SIGNAL SCORING
  Previously all signals (trend, momentum, etc.) counted equally.
  Now each signal is weighted based on which REGIME we're in.

  In a TRENDING market → Trend and Volume signals matter most
                         (following the trend is the safest strategy)
  In a MEAN-REVERTING  → Mean reversion and Stoch RSI matter most
                         (fading the move works better than following it)
  In a RANDOM market   → All signals are distrusted equally (big penalty)

SIGNAL WEIGHTS BY REGIME:
  ┌───────────────┬────────┬──────────┬─────────────┬────────┬───────────┐
  │ Regime        │ Trend  │ Momentum │ Mean Rev    │ Volume │ Stoch RSI │
  ├───────────────┼────────┼──────────┼─────────────┼────────┼───────────┤
  │ trending      │ 0.40   │ 0.25     │ 0.10        │ 0.15   │ 0.10      │
  │ mean_reverting│ 0.15   │ 0.20     │ 0.35        │ 0.15   │ 0.15      │
  │ random        │ 0.20   │ 0.20     │ 0.20        │ 0.20   │ 0.20      │
  └───────────────┴────────┴──────────┴─────────────┴────────┴───────────┘

HOW IT WORKS — 7 factors combined:
  1. Weighted Signal Strength  — Regime-appropriate signal consensus
  2. Directional Consensus     — Are all signals pointing same way?
  3. Dispersion Penalty        — Punish contradictory signals
  4. Regime Factor             — Trending markets get a boost
  5. Volatility Adjustment     — Extreme volatility penalised
  6. Trend Alignment Bonus     — Bonus when regime aligns with trend signal
  7. Sigmoid Clamp             — Smooth S-curve output for decisive scores

WHY SIGMOID?
  Maps raw score through an S-curve so values naturally cluster below 0.4
  or above 0.6 — fewer ambiguous "maybe" scores near the 50% decision line.
"""

import math


# ── Regime-specific signal weights ────────────────────────────────────────────
# Each weight says "how much does this signal matter in this market type?"
# Weights within each row sum to 1.0.
REGIME_WEIGHTS = {
    "trending": {
        "trend":         0.40,   # Following the trend is most reliable here
        "momentum":      0.25,   # MACD/RSI confirm the trend
        "mean_reversion":0.10,   # Low weight: mean reversion fights the trend (dangerous)
        "volume":        0.15,   # Volume confirms institutional participation
        "stoch_rsi":     0.10,   # Useful but less critical in trending markets
    },
    "mean_reverting": {
        "trend":         0.15,   # Low weight: trend signals are misleading here
        "momentum":      0.20,   # Moderate: momentum shows reversal speed
        "mean_reversion":0.35,   # High: Bollinger Band signals most reliable here
        "volume":        0.15,   # Volume flow confirms reversals
        "stoch_rsi":     0.15,   # Stoch RSI excellent for timing bounces
    },
    "random": {
        "trend":         0.20,   # Equal weights — no regime advantage
        "momentum":      0.20,
        "mean_reversion":0.20,
        "volume":        0.20,
        "stoch_rsi":     0.20,
    },
}

# Default weights (equal) used when regime is unknown or signal key is missing
DEFAULT_WEIGHTS = {k: 0.20 for k in ["trend", "momentum", "mean_reversion", "volume", "stoch_rsi"]}


def compute_confidence(signals: dict, regime: str, atr_percentile: float) -> float:
    """
    Calculates a regime-weighted conviction score (0.0–1.0) for the proposed trade.

    Args:
        signals        (dict):  5 technical signals from strategy_engine.py
                                e.g. {"trend": 1, "momentum": 0.6, "mean_reversion": 0,
                                      "volume": 1, "stoch_rsi": -1}
        regime         (str):   "trending" | "mean_reverting" | "random"
        atr_percentile (float): 0–1 where current volatility sits vs recent history

    Returns:
        float: Confidence score rounded to 3 decimal places. Example: 0.682
    """
    # ── Early exit if no signals at all ──────────────────────────────────────
    if not signals or not any(signals.values()):
        return 0.0

    # ── Get regime-appropriate weights ────────────────────────────────────────
    weights = REGIME_WEIGHTS.get(regime, DEFAULT_WEIGHTS)

    # ── Factor 1: Regime-Weighted Signal Strength ─────────────────────────────
    # Instead of all signals counting equally, each is multiplied by its regime weight.
    # A trend signal in a trending market contributes 4x more than in a random market.
    weighted_vals = []
    weight_total  = 0.0
    for key, weight in weights.items():
        val = signals.get(key, 0)
        weighted_vals.append(val * weight)
        weight_total += weight * abs(val)   # Track total possible weighted magnitude

    # Weighted sum (signed — preserves direction)
    weighted_sum = sum(weighted_vals)

    # ── Factor 2: Directional Consensus ──────────────────────────────────────
    # How much do signals AGREE on direction? Perfect agreement = 1.0
    # Mix of +1 and -1 signals cancels out toward 0.0
    abs_weighted_sum = sum(abs(v) for v in weighted_vals)
    consensus = abs(weighted_sum) / (abs_weighted_sum + 1e-9)

    # ── Factor 3: Dispersion Penalty ─────────────────────────────────────────
    # High variance in signal values = contradictory signals = noisy market
    vals = list(signals.values())
    mean_val = sum(vals) / len(vals) if vals else 0
    variance = sum((v - mean_val)**2 for v in vals) / (len(vals) + 1e-9)
    dispersion_penalty = 1 - min(variance * 0.5, 0.8)   # Max 80% penalty

    # ── Factor 4: Regime Multiplier ───────────────────────────────────────────
    # Trending and mean-reverting markets are more predictable than random
    if regime == "trending":
        regime_factor = 1.10    # 10% boost — structure helps the model
    elif regime == "mean_reverting":
        regime_factor = 1.05    # 5% boost — structure present, harder to time
    else:
        regime_factor = 0.72    # 28% penalty — random market, low reliability

    # ── Factor 5: Volatility Adjustment ──────────────────────────────────────
    # ATR percentile = where current volatility sits vs recent history
    # Both extremes are dangerous for signal reliability
    if atr_percentile > 0.95:
        vol_factor = 0.65    # Extreme volatility: crash/spike risk
    elif atr_percentile > 0.80:
        vol_factor = 0.85    # Elevated but manageable
    elif atr_percentile < 0.05:
        vol_factor = 0.75    # Dead market: illiquid, hard to fill orders
    else:
        vol_factor = 1.0     # Normal range

    # ── Factor 6: Trend Alignment Bonus ──────────────────────────────────────
    # Extra bonus when we're in a trending market AND the trend signal confirms the move
    if regime == "trending" and signals.get("trend", 0) != 0:
        alignment_bonus = 1.08    # 8% bonus for perfect regime-signal alignment
    else:
        alignment_bonus = 1.0

    # ── Factor 7: Raw Composite Score ─────────────────────────────────────────
    # consensus captures signal agreement (key driver)
    # Other factors modulate up or down based on conditions
    raw_conf = (
        consensus          *  # Directional agreement (0–1, most important)
        dispersion_penalty *  # Penalise contradictory signals
        regime_factor      *  # Regime type multiplier
        vol_factor         *  # Volatility safety adjustment
        alignment_bonus       # Regime-trend alignment bonus
    )

    # ── Sigmoid Stabilization ────────────────────────────────────────────────
    # Maps raw score through S-curve: scores become decisively low or high
    # Steep transition around 0.5 reduces ambiguous "maybe" scores
    # Formula: 1 / (1 + e^(-k × (raw - 0.5)))   k=5 = steeper curve
    stabilized = 1 / (1 + math.exp(-5 * (raw_conf - 0.5)))

    return round(min(stabilized, 1.0), 3)