"""
test_confidence.py  —  Unit Tests for Enhanced Confidence Engine
================================================================
Tests that the v2 confidence.py produces full dynamic range (0–100)
and correctly applies regime and volatility adjustments.

Run: python -m pytest test_confidence.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from confidence import compute_confidence

# ── Fixtures ──────────────────────────────────────────────────────────────────

ALL_BULLISH   = {"trend": 1,  "momentum":  1.0,  "mean_reversion": 1,  "volume": 1,  "stoch_rsi": 1}
ALL_BEARISH   = {"trend": -1, "momentum": -1.0,  "mean_reversion": -1, "volume": -1, "stoch_rsi": -1}
ALL_NEUTRAL   = {"trend": 0,  "momentum":  0.0,  "mean_reversion": 0,  "volume": 0,  "stoch_rsi": 0}
MIXED_BULLISH = {"trend": 1,  "momentum":  0.6,  "mean_reversion": 0,  "volume": 1,  "stoch_rsi": -1}
MIXED_SPLIT   = {"trend": 1,  "momentum": -1.0,  "mean_reversion": 1,  "volume": -1, "stoch_rsi": 1}
EMPTY_SIGNALS = {}

NORMAL_VOL   = 0.50
LOW_VOL      = 0.03
HIGH_VOL     = 0.85
EXTREME_VOL  = 0.97


# ── Range Tests (Core Fix) ────────────────────────────────────────────────────

class TestConfidenceRange:
    """Verifies that the full 0–1 dynamic range is now accessible."""

    def test_all_bullish_trending_gives_high_confidence(self):
        score = compute_confidence(ALL_BULLISH, "trending", NORMAL_VOL)
        assert score >= 0.75, f"Expected >= 0.75 for all-bullish trending, got {score}"

    def test_all_bearish_trending_gives_high_confidence(self):
        """Confidence measures conviction, not direction — bearish should also be high."""
        score = compute_confidence(ALL_BEARISH, "trending", NORMAL_VOL)
        assert score >= 0.75, f"Expected >= 0.75 for all-bearish trending, got {score}"

    def test_all_neutral_gives_low_confidence(self):
        score = compute_confidence(ALL_NEUTRAL, "trending", NORMAL_VOL)
        assert score <= 0.30, f"Expected <= 0.30 for all-neutral, got {score}"

    def test_empty_signals_returns_zero(self):
        score = compute_confidence(EMPTY_SIGNALS, "trending", NORMAL_VOL)
        assert score == 0.0, f"Expected 0.0 for empty signals, got {score}"

    def test_score_never_exceeds_one(self):
        score = compute_confidence(ALL_BULLISH, "trending", NORMAL_VOL)
        assert score <= 1.0, f"Score exceeded 1.0: {score}"

    def test_score_never_below_zero(self):
        score = compute_confidence(ALL_BEARISH, "volatile", EXTREME_VOL)
        assert score >= 0.0, f"Score below 0.0: {score}"


# ── Regime Tests ──────────────────────────────────────────────────────────────

class TestRegimeEffect:
    """Verifies regime-based confidence adjustments."""

    def test_trending_outscores_random_for_same_signals(self):
        trending = compute_confidence(ALL_BULLISH, "trending", NORMAL_VOL)
        random   = compute_confidence(ALL_BULLISH, "random",   NORMAL_VOL)
        assert trending > random, f"Trending ({trending}) should > random ({random})"

    def test_volatile_gives_lowest_confidence(self):
        volatile = compute_confidence(ALL_BULLISH, "volatile", NORMAL_VOL)
        random   = compute_confidence(ALL_BULLISH, "random",   NORMAL_VOL)
        assert volatile < random, f"Volatile ({volatile}) should < random ({random})"

    def test_mean_reverting_outscores_random(self):
        mrv    = compute_confidence(ALL_BULLISH, "mean_reverting", NORMAL_VOL)
        random = compute_confidence(ALL_BULLISH, "random",         NORMAL_VOL)
        assert mrv > random, f"Mean-reverting ({mrv}) should > random ({random})"

    def test_all_four_regimes_produce_valid_output(self):
        for regime in ["trending", "mean_reverting", "volatile", "random"]:
            score = compute_confidence(ALL_BULLISH, regime, NORMAL_VOL)
            assert 0.0 <= score <= 1.0, f"Regime '{regime}' produced out-of-range: {score}"


# ── Volatility Adjustment Tests ───────────────────────────────────────────────

class TestVolatilityAdjustment:
    """Verifies ATR percentile penalises extreme conditions."""

    def test_extreme_volatility_penalises_score(self):
        normal  = compute_confidence(ALL_BULLISH, "trending", NORMAL_VOL)
        extreme = compute_confidence(ALL_BULLISH, "trending", EXTREME_VOL)
        assert extreme < normal, f"Extreme vol ({extreme}) should < normal vol ({normal})"

    def test_low_volatility_penalises_score(self):
        normal = compute_confidence(ALL_BULLISH, "trending", NORMAL_VOL)
        low    = compute_confidence(ALL_BULLISH, "trending", LOW_VOL)
        assert low < normal, f"Low vol ({low}) should < normal vol ({normal})"


# ── Mixed Signal Tests ────────────────────────────────────────────────────────

class TestMixedSignals:
    """Verifies mixed signals produce appropriate mid-range scores."""

    def test_mixed_split_below_threshold(self):
        score = compute_confidence(MIXED_SPLIT, "random", NORMAL_VOL)
        assert score < 0.55, f"Perfectly split signals should be < 0.55, got {score}"

    def test_mixed_bullish_in_trending_within_range(self):
        score = compute_confidence(MIXED_BULLISH, "trending", NORMAL_VOL)
        assert 0.0 <= score <= 1.0, f"Mixed bullish trending out of range: {score}"

    def test_continuous_momentum_range(self):
        """Verify fractional momentum values (0.6) are handled correctly."""
        signals = {"trend": 1, "momentum": 0.6, "mean_reversion": 0, "volume": 1, "stoch_rsi": 0}
        score = compute_confidence(signals, "trending", NORMAL_VOL)
        assert 0.0 <= score <= 1.0, f"Fractional momentum out of range: {score}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
