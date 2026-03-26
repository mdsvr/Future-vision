"""
explanation_builder.py  —  Structured Indicator Reasoning Engine
=================================================================
Builds rich, human-readable trading explanations from raw indicator
states. This is a fully offline, deterministic system — no API calls.

PIPELINE:
  Indicator Values
    → State Classification (overbought / bullish / neutral etc.)
    → Per-Indicator Phrase Lookup
    → Contextual Sentence Assembly
    → Synthesis Conclusion
    → Final 4–6 sentence explanation paragraph

USAGE:
    from reasoning_engine.explanation_builder import build_explanation

    text = build_explanation(
        signals       = {"trend": 1, "momentum": 0.6, ...},
        regime        = "trending",
        rsi_val       = 66.2,
        macd_val      = 0.15,
        macd_sig_val  = 0.08,
        stoch_val     = 0.82,
        atr_percentile= 0.42,
        confidence    = 0.74,
    )
"""

# ── RSI Interpretation Templates ──────────────────────────────────────────────
_RSI_PHRASES = {
    "overbought": (
        "RSI ({val:.1f}) has entered overbought territory, indicating momentum "
        "is reaching exhaustion and a near-term pullback or consolidation is probable."
    ),
    "approaching_overbought": (
        "RSI ({val:.1f}) is approaching the overbought zone — upward momentum remains "
        "intact but is showing signs of fatigue near historical resistance levels."
    ),
    "oversold": (
        "RSI ({val:.1f}) signals deeply oversold conditions, raising the probability "
        "of a mean-reversion bounce or short-covering rally from current levels."
    ),
    "approaching_oversold": (
        "RSI ({val:.1f}) is nearing oversold territory, suggesting sellers are "
        "becoming overextended and a technical recovery could materialise soon."
    ),
    "neutral_bullish": (
        "RSI ({val:.1f}) sits in a bullish neutral zone, reflecting moderate upward "
        "momentum without the exhaustion risk associated with overbought readings."
    ),
    "neutral_bearish": (
        "RSI ({val:.1f}) is in a bearish neutral zone, indicating mild downward "
        "pressure without a decisive oversold signal to trigger a meaningful reversal."
    ),
    "neutral": (
        "RSI ({val:.1f}) is in a mid-range neutral zone, providing no strong "
        "directional bias in either direction at this stage."
    ),
}

# ── MACD Interpretation Templates ─────────────────────────────────────────────
_MACD_PHRASES = {
    "strong_bullish": (
        "MACD is showing a strong bullish divergence from its signal line, "
        "confirming accelerating upward momentum with institutional buying pressure."
    ),
    "bullish_cross": (
        "MACD has crossed above its signal line, signalling a shift toward bullish "
        "momentum and confirming the early stages of an upward continuation move."
    ),
    "weak_bullish": (
        "MACD holds a marginal edge above its signal line — momentum is leaning "
        "bullish but conviction is limited; confirmation from volume would strengthen this."
    ),
    "flat": (
        "MACD is closely tracking its signal line, indicating momentum is "
        "consolidating without a clear directional bias or breakout catalyst."
    ),
    "weak_bearish": (
        "MACD is fractionally below its signal line — a mild bearish lean is present "
        "but insufficient alone to signal a confirmed downtrend without further deterioration."
    ),
    "bearish_cross": (
        "MACD has crossed below its signal line, confirming a momentum shift toward "
        "bearish pressure and increasing the probability of downside continuation."
    ),
    "strong_bearish": (
        "MACD shows a significant bearish divergence from its signal line, reflecting "
        "accelerating downward momentum consistent with sustained distribution activity."
    ),
}

# ── Volume / OBV Interpretation Templates ─────────────────────────────────────
_VOLUME_PHRASES = {
    "strong_bullish": (
        "OBV is rising sharply, indicating institutional accumulation — large "
        "traders are positioning on the buy side with increasing conviction."
    ),
    "bullish": (
        "OBV slope is positive, confirming that volume flow supports the upward "
        "price move and that buying participation outweighs selling pressure."
    ),
    "neutral": (
        "OBV is relatively flat, suggesting that neither buyers nor sellers are "
        "asserting dominance through volume — conviction is absent on both sides."
    ),
    "bearish": (
        "OBV slope is negative, signalling that volume is flowing out of the "
        "asset — a pattern consistent with smart-money distribution activity."
    ),
    "strong_bearish": (
        "OBV is declining sharply, indicating aggressive institutional distribution. "
        "Heavy volume on down moves outnumbers buying, a classic bearish divergence signal."
    ),
}

# ── EMA Trend Interpretation Templates ────────────────────────────────────────
_TREND_PHRASES = {
    "strong_bullish": (
        "Price is trading above both EMA-50 and EMA-200 in a golden alignment — "
        "the primary trend structure is bullish and supports continuation setups."
    ),
    "neutral": (
        "EMA-50 and EMA-200 are in a mixed or crossing configuration, reflecting "
        "an absence of clear trend structure. Directionality is indeterminate currently."
    ),
    "strong_bearish": (
        "Price is trading below both EMA-50 and EMA-200 in a death alignment — "
        "the trend structure is bearish and favours continuation of downside pressure."
    ),
}

# ── Stochastic RSI Templates ───────────────────────────────────────────────────
_STOCH_PHRASES = {
    "overbought": (
        "Stochastic RSI ({val:.2f}) is in extreme overbought territory — a momentum "
        "reversal or short-term pullback is statistically elevated from current levels."
    ),
    "elevated": (
        "Stochastic RSI ({val:.2f}) is elevated but not yet in the critical overbought "
        "zone — momentum is strong with some remaining upside window before exhaustion."
    ),
    "oversold": (
        "Stochastic RSI ({val:.2f}) is in extreme oversold territory, historically "
        "associated with sharp technical rebounds and mean-reversion opportunities."
    ),
    "depressed": (
        "Stochastic RSI ({val:.2f}) is low but not yet at critical oversold levels — "
        "momentum is weak with potential for further deterioration before a clear reversal."
    ),
    "neutral": (
        "Stochastic RSI ({val:.2f}) is in a neutral mid-range, offering no "
        "extreme timing signal for entry or exit at this stage."
    ),
}

# ── Regime Context Templates ───────────────────────────────────────────────────
_REGIME_PHRASES = {
    "trending": (
        "The market regime is classified as TRENDING (Hurst memory structure confirmed), "
        "favouring trend-following strategies over mean-reversion approaches."
    ),
    "mean_reverting": (
        "The market regime is MEAN-REVERTING — price is exhibiting oscillatory "
        "behaviour, making fading-the-move strategies more effective than trend-following."
    ),
    "volatile": (
        "The market is in a VOLATILE SPIKE regime — ATR is significantly elevated "
        "above historical norms. Predictability is reduced; position sizing caution is warranted."
    ),
    "random": (
        "The market regime is RANDOM — no structural pattern is detectable. "
        "Signal reliability is reduced across all indicators during this condition."
    ),
}

# ── Volatility Context Templates ───────────────────────────────────────────────
_VOLATILITY_PHRASES = {
    "extreme": (
        "Volatility is at an extreme historical percentile ({pct:.0%}) — "
        "wide stop-loss distances are required, and risk-of-ruin is elevated."
    ),
    "elevated": (
        "Volatility is above normal at the {pct:.0%} historical percentile — "
        "position sizing should be reduced to maintain consistent risk exposure."
    ),
    "normal": (
        "Volatility is within a normal historical range ({pct:.0%} percentile), "
        "providing stable conditions for technical signal reliability."
    ),
    "low": (
        "Volatility is historically low ({pct:.0%} percentile) — the market may be "
        "compressing ahead of a breakout move; caution on stale signals."
    ),
}


# ── State Classifiers ──────────────────────────────────────────────────────────

def _classify_rsi(rsi_val: float) -> str:
    if rsi_val > 75:    return "overbought"
    if rsi_val > 65:    return "approaching_overbought"
    if rsi_val < 25:    return "oversold"
    if rsi_val < 35:    return "approaching_oversold"
    if rsi_val > 50:    return "neutral_bullish"
    if rsi_val < 50:    return "neutral_bearish"
    return "neutral"


def _classify_macd(macd_val: float, macd_sig_val: float) -> str:
    diff = macd_val - macd_sig_val
    denom = abs(macd_sig_val) + abs(macd_val) + 1e-9
    ratio = diff / denom
    if ratio > 0.25:    return "strong_bullish"
    if ratio > 0.05:    return "bullish_cross"
    if ratio > 0.01:    return "weak_bullish"
    if abs(ratio) <= 0.01: return "flat"
    if ratio > -0.05:   return "weak_bearish"
    if ratio > -0.25:   return "bearish_cross"
    return "strong_bearish"


def _classify_volume(vol_signal: float) -> str:
    if vol_signal >= 1:     return "strong_bullish"
    if vol_signal > 0:      return "bullish"
    if vol_signal == 0:     return "neutral"
    if vol_signal > -1:     return "bearish"
    return "strong_bearish"


def _classify_stoch(stoch_val: float) -> str:
    if stoch_val > 0.85:    return "overbought"
    if stoch_val > 0.65:    return "elevated"
    if stoch_val < 0.15:    return "oversold"
    if stoch_val < 0.35:    return "depressed"
    return "neutral"


def _classify_volatility(atr_percentile: float) -> str:
    if atr_percentile > 0.90:   return "extreme"
    if atr_percentile > 0.70:   return "elevated"
    if atr_percentile < 0.15:   return "low"
    return "normal"


def _classify_trend(trend_signal: int) -> str:
    if trend_signal > 0:    return "strong_bullish"
    if trend_signal < 0:    return "strong_bearish"
    return "neutral"


# ── Conclusion Builder ─────────────────────────────────────────────────────────

def _build_conclusion(signals: dict, confidence: float, regime: str) -> str:
    """Synthesises a single-sentence conclusion from the overall signal picture."""
    direction_sum = sum(signals.values())
    bull_count    = sum(1 for v in signals.values() if v > 0)
    bear_count    = sum(1 for v in signals.values() if v < 0)
    total         = len(signals)

    if confidence < 0.45:
        return (
            "Combined interpretation suggests insufficient conviction to act — "
            "the risk-reward profile does not meet minimum thresholds. Action: HOLD."
        )

    if direction_sum > 0 and bull_count >= (total * 0.6):
        strength = "strong" if confidence > 0.72 else "moderate"
        return (
            f"Combined interpretation indicates {strength} bullish probability "
            f"({bull_count}/{total} indicators aligned). Risk-adjusted entry is warranted."
        )

    if direction_sum < 0 and bear_count >= (total * 0.6):
        strength = "strong" if confidence > 0.72 else "moderate"
        return (
            f"Combined interpretation indicates {strength} bearish pressure "
            f"({bear_count}/{total} indicators aligned). Defensive positioning is supported."
        )

    return (
        "Indicators are mixed with no clear consensus direction. "
        "A HOLD stance is prudent until signals align more decisively."
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def build_explanation(
    signals: dict,
    regime: str,
    rsi_val: float,
    macd_val: float,
    macd_sig_val: float,
    stoch_val: float,
    atr_percentile: float,
    confidence: float = 0.5,
) -> str:
    """
    Builds a structured, human-readable trading explanation.

    Args:
        signals       (dict):  Signal dict {trend, momentum, mean_reversion, volume, stoch_rsi}
        regime        (str):   Market regime string
        rsi_val       (float): Raw RSI value (0–100)
        macd_val      (float): MACD line value
        macd_sig_val  (float): MACD signal line value
        stoch_val     (float): Stochastic RSI value (0.0–1.0)
        atr_percentile(float): ATR historical percentile (0.0–1.0)
        confidence    (float): Confidence score (0.0–1.0); used for conclusion

    Returns:
        str: 4–6 sentence structured explanation paragraph
    """
    lines = []

    # 1. Regime context
    regime_phrase = _REGIME_PHRASES.get(regime, _REGIME_PHRASES["random"])
    lines.append(regime_phrase)

    # 2. Trend (EMA alignment)
    trend_state  = _classify_trend(signals.get("trend", 0))
    trend_phrase = _TREND_PHRASES[trend_state]
    lines.append(trend_phrase)

    # 3. RSI momentum
    rsi_state  = _classify_rsi(rsi_val)
    rsi_phrase = _RSI_PHRASES[rsi_state].format(val=rsi_val)
    lines.append(rsi_phrase)

    # 4. MACD momentum
    macd_state  = _classify_macd(macd_val, macd_sig_val)
    macd_phrase = _MACD_PHRASES[macd_state]
    lines.append(macd_phrase)

    # 5. Volume flow (only if non-neutral to avoid padding)
    vol_state = _classify_volume(signals.get("volume", 0))
    if vol_state != "neutral":
        lines.append(_VOLUME_PHRASES[vol_state])

    # 6. Stochastic RSI (only if at an extreme — avoids noise in neutral zones)
    stoch_state = _classify_stoch(stoch_val)
    if stoch_state not in ("neutral",):
        stoch_phrase = _STOCH_PHRASES[stoch_state].format(val=stoch_val)
        lines.append(stoch_phrase)

    # 7. Volatility context
    vol_env     = _classify_volatility(atr_percentile)
    vol_phrase  = _VOLATILITY_PHRASES[vol_env].format(pct=atr_percentile)
    lines.append(vol_phrase)

    # 8. Synthesis conclusion
    lines.append(_build_conclusion(signals, confidence, regime))

    return " ".join(lines)
