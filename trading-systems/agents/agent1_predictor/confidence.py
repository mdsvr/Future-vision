import math

def compute_confidence(signals, regime, atr_percentile):
    """
    Calculates the 'Conviction Score' (0-1) for the proposed trade.
    Higher scores mean multiple strategies are in agreement and the market state is stable.
    """
    values = list(signals.values())

    if not any(values):
        return 0.0

    # -------------------------
    # 1️⃣ Signal Strength
    # -------------------------
    # Measures the 'loudness' of signals. A 1.0 momentum is louder than a 0.5 momentum.
    abs_values = [abs(v) for v in values]
    strength = sum(abs_values) / len(abs_values)

    # Non-linear boost to emphasize when indicators are screaming 'GO!'
    strength = strength ** 1.2

    # -------------------------
    # 2️⃣ Directional Consensus
    # -------------------------
    # Are all signals pointing the same way? 
    # If Strategy A says BUY (+1) and B says SELL (-1), consensus is 0.
    consensus = abs(sum(values)) / (sum(abs_values) + 1e-9)

    # -------------------------
    # 3️⃣ Dispersion Penalty
    # -------------------------
    # High variance between signals indicates confusion/market noise.
    variance = sum((v - sum(values)/len(values))**2 for v in values) / len(values)
    dispersion_penalty = 1 - min(variance, 1)

    # -------------------------
    # 4️⃣ Regime Factor
    # -------------------------
    # The agent performs best in trending or clear mean-reverting markets.
    # 'Random' (sideways) markets get a 30% reduction in confidence.
    if regime == "trending":
        regime_factor = 1.05
    elif regime == "mean_reverting":
        regime_factor = 0.95
    else:
        regime_factor = 0.7
    
    # -------------------------
    # 5️⃣ Volatility Adjustment
    # -------------------------
    # Extreme volatility (ATR > 95th percentile) is risky and penalised.
    # Dead markets (ATR < 5th percentile) lack liquidity/movement and are also penalised.
    if atr_percentile > 0.95:
        vol_factor = 0.65   # Chaos penalty
    elif atr_percentile > 0.80:
        vol_factor = 0.85
    elif atr_percentile < 0.05:
        vol_factor = 0.75   # Low-liquidity penalty
    else:
        vol_factor = 1.0

    # -------------------------
    # 6️⃣ Trend Alignment Bonus
    # -------------------------
    # If we are in a 'Trending' regime, following the trend signal earns a 5% bonus.
    if regime == "trending" and signals.get("trend", 0) != 0:
        alignment_bonus = 1.05
    else:
        alignment_bonus = 1.0

    # -------------------------
    # 7️⃣ Composite Score Calculation
    # -------------------------
    raw_conf = (
        strength *
        consensus *
        dispersion_penalty *
        regime_factor *
        vol_factor *
        alignment_bonus
    )

    # -------------------------
    # 8️⃣ Sigmoid Stabilization
    # -------------------------
    # We squish the raw score through a sigmoid function to make the 
    # transition from 'Maybe' to 'Yes' more decisive around the 0.5 mark.
    stabilized = 1 / (1 + math.exp(-4 * (raw_conf - 0.5)))

    # Return as a 3-decimal float for better reporting
    return round(min(stabilized, 1.0), 3)