"""
confidence.py  —  Trade Conviction Scorer
==========================================
Answers the question: "How SURE is the AI about this trade?"

The output is a number from 0.0 to 1.0 (shown as 0% to 100%).

  Below 0.55 (55%) → Agent says HOLD (not confident enough to act)
  Above 0.55 (55%) → Agent can consider BUY or SELL

UPGRADE v2: FULL-RANGE PROBABILISTIC CONFIDENCE ENGINE
  Previously: scores clustered in 50–75 due to compressed raw inputs.
  Now:        scores dynamically span 0–100 based on signal conviction.

  Key improvements:
    1. Signal Magnitude Factor  — rewards unanimously strong signals
    2. Raw composite scaled 1.5× — spreads sigmoid input across full range
    3. Volatile regime           — 4th regime for spike/crisis markets
    4. Regime penalty for noise  — random/volatile markets get steep cuts

SIGNAL WEIGHTS BY REGIME:
  ┌───────────────┬────────┬──────────┬─────────────┬────────┬───────────┐
  │ Regime        │ Trend  │ Momentum │ Mean Rev    │ Volume │ Stoch RSI │
  ├───────────────┼────────┼──────────┼─────────────┼────────┼───────────┤
  │ trending      │ 0.40   │ 0.25     │ 0.10        │ 0.15   │ 0.10      │
  │ mean_reverting│ 0.15   │ 0.20     │ 0.35        │ 0.15   │ 0.15      │
  │ volatile      │ 0.10   │ 0.15     │ 0.35        │ 0.25   │ 0.15      │
  │ random        │ 0.20   │ 0.20     │ 0.20        │ 0.20   │ 0.20      │
  └───────────────┴────────┴──────────┴─────────────┴────────┴───────────┘

HOW IT WORKS — 8 factors combined:
  1. Weighted Signal Strength  — Regime-appropriate signal consensus
  2. Signal Magnitude          — How strong are the signals (not just direction)?
  3. Directional Consensus     — Are all signals pointing the same way?
  4. Dispersion Penalty        — Punish contradictory signals
  5. Regime Factor             — Trending gets boost; volatile/random get cuts
  6. Volatility Adjustment     — Extreme volatility penalised
  7. Trend Alignment Bonus     — Bonus when regime and trend signal align
  8. Sigmoid Clamp (scaled)    — 1.5× scaling for full dynamic range
"""

import math


# ── Regime-specific signal weights ────────────────────────────────────────────
REGIME_WEIGHTS = {
    "trending": {
        "trend":          0.40,   # Following the trend is most reliable here
        "momentum":       0.25,   # MACD/RSI confirm the trend
        "mean_reversion": 0.10,   # Low weight: mean reversion fights the trend
        "volume":         0.15,   # Volume confirms institutional participation
        "stoch_rsi":      0.10,   # Useful but less critical in trending markets
    },
    "mean_reverting": {
        "trend":          0.15,   # Low: trend signals are misleading here
        "momentum":       0.20,   # Moderate: momentum shows reversal speed
        "mean_reversion": 0.35,   # High: Bollinger Band signals most reliable
        "volume":         0.15,   # Volume flow confirms reversals
        "stoch_rsi":      0.15,   # Excellent for timing bounces
    },
    "volatile": {
        "trend":          0.10,   # Trend is meaningless in a spike/crisis
        "momentum":       0.15,   # Momentum signal is noisy during spikes
        "mean_reversion": 0.35,   # Snap-backs are the dominant pattern
        "volume":         0.25,   # Volume expansion is the key crisis signal
        "stoch_rsi":      0.15,   # Useful for timing reversal entry
    },
    "random": {
        "trend":          0.20,   # Equal weights — no regime advantage
        "momentum":       0.20,
        "mean_reversion": 0.20,
        "volume":         0.20,
        "stoch_rsi":      0.20,
    },
}

# Default weights (equal) used when regime is unknown or signal key is missing
DEFAULT_WEIGHTS = {k: 0.20 for k in ["trend", "momentum", "mean_reversion", "volume", "stoch_rsi"]}


def compute_confidence(signals: dict, regime: str, atr_percentile: float) -> float:
    """
    Calculates a regime-weighted conviction score (0.0–1.0) for the proposed trade.

    v2 improvements:
    - Signal magnitude factor rewards strong unambiguous signals
    - 1.5× scaling of raw composite pushes sigmoid into its full dynamic range
    - 4th 'volatile' regime with appropriate weights and steep penalty
    - Output now dynamically spans 0.0–1.0 (was clustered at 0.50–0.75)

    Args:
        signals        (dict):  5 technical signals from strategy_engine.py
                                e.g. {"trend": 1, "momentum": 0.6, "mean_reversion": 0,
                                      "volume": 1, "stoch_rsi": -1}
        regime         (str):   "trending" | "mean_reverting" | "volatile" | "random"
        atr_percentile (float): 0–1 where current volatility sits vs recent history

    Returns:
        float: Confidence score rounded to 3 decimal places, range 0.0–1.0.
               Multiply by 100 for percentage display.
    """
    # ── Early exit if no signals at all ──────────────────────────────────────
    if not signals or not any(signals.values()):
        return 0.0

    # ── Get regime-appropriate weights ────────────────────────────────────────
    weights = REGIME_WEIGHTS.get(regime, DEFAULT_WEIGHTS)

    # ── Factor 1: Regime-Weighted Signal Strength ─────────────────────────────
    weighted_vals = []
    for key, weight in weights.items():
        val = signals.get(key, 0)
        weighted_vals.append(val * weight)

    weighted_sum = sum(weighted_vals)

    # ── Factor 2: Signal Magnitude ────────────────────────────────────────────
    # Rewards signals that are strongly positive or negative (not just directional).
    # Absolute weighted sum / maximum possible weighted sum → 0.0 to 1.0.
    # A signal of 0.6 * weight 0.4 contributes 0.24 vs a binary 1 * 0.4 = 0.40.
    # This factor expands the range for strong-conviction readings.
    max_possible = sum(abs(w) for w in weights.values())  # = 1.0 when weights sum to 1
    abs_weighted = sum(abs(v) for v in weighted_vals)
    signal_magnitude = abs_weighted / (max_possible + 1e-9)

    # ── Factor 3: Directional Consensus ──────────────────────────────────────
    # How much do signals AGREE on direction? Perfect agreement = 1.0
    consensus = abs(weighted_sum) / (abs_weighted + 1e-9)

    # ── Factor 4: Dispersion Penalty ─────────────────────────────────────────
    # High variance = contradictory signals = noisy market
    vals = list(signals.values())
    mean_val = sum(vals) / len(vals) if vals else 0
    variance = sum((v - mean_val) ** 2 for v in vals) / (len(vals) + 1e-9)
    dispersion_penalty = 1 - min(variance * 0.5, 0.8)   # Max 80% penalty

    # ── Factor 5: Regime Multiplier ───────────────────────────────────────────
    regime_factor = {
        "trending":       1.10,   # 10% boost — clear structure
        "mean_reverting": 1.05,   # 5% boost — structure present, harder to time
        "volatile":       0.60,   # 40% penalty — spike/crisis, low reliability
        "random":         0.72,   # 28% penalty — no structure
    }.get(regime, 0.72)

    # ── Factor 6: Volatility Adjustment ──────────────────────────────────────
    if atr_percentile > 0.95:
        vol_factor = 0.65    # Extreme volatility: crash/spike risk
    elif atr_percentile > 0.80:
        vol_factor = 0.85    # Elevated but manageable
    elif atr_percentile < 0.05:
        vol_factor = 0.75    # Dead market: illiquid, hard to fill
    else:
        vol_factor = 1.0     # Normal range

    # ── Factor 7: Trend Alignment Bonus ──────────────────────────────────────
    if regime == "trending" and signals.get("trend", 0) != 0:
        alignment_bonus = 1.08    # 8% bonus for perfect regime-signal alignment
    else:
        alignment_bonus = 1.0

    # ── Factor 8: Raw Composite Score (scaled for full sigmoid range) ──────────
    # consensus   × magnitude gives a richer raw score than consensus alone.
    # Scaling by 1.5× spreads the sigmoid input from its previous [0.3–0.7]
    # compression zone into [0.45–1.05], unlocking scores from ~10% to ~95%.
    raw_conf = (
        consensus          *   # Directional agreement (key driver)
        signal_magnitude   *   # Strength of signals (NEW: range expander)
        dispersion_penalty *   # Penalise contradictory signals
        regime_factor      *   # Regime type multiplier
        vol_factor         *   # Volatility safety adjustment
        alignment_bonus        # Regime-trend alignment bonus
    ) * 1.5                    # Scale factor: unlocks full sigmoid range

    # ── Sigmoid Stabilization ────────────────────────────────────────────────
    # k=6 gives a steeper S-curve: scores cluster decisively below 0.4 or above 0.6
    stabilized = 1 / (1 + math.exp(-6 * (raw_conf - 0.5)))

    return round(min(stabilized, 1.0), 3)