"""
test_reasoning.py  —  Unit Tests for Explanation Builder
=========================================================
Tests that explanation_builder.build_explanation() produces
non-empty, well-formed structured narratives for all indicator
state permutations.

Run: python -m pytest test_reasoning.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from reasoning_engine.explanation_builder import (
    build_explanation,
    _classify_rsi, _classify_macd, _classify_volume,
    _classify_stoch, _classify_volatility, _classify_trend,
    _build_conclusion,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

ALL_BULLISH = {"trend": 1, "momentum": 1.0, "mean_reversion": 1, "volume": 1, "stoch_rsi": 1}
ALL_BEARISH = {"trend":-1, "momentum":-1.0, "mean_reversion":-1, "volume":-1, "stoch_rsi":-1}
ALL_NEUTRAL = {"trend": 0, "momentum": 0.0, "mean_reversion": 0,  "volume": 0, "stoch_rsi": 0}
MIXED       = {"trend": 1, "momentum": 0.5, "mean_reversion":-1,  "volume": 1, "stoch_rsi":-1}


# ── State Classifier Tests ────────────────────────────────────────────────────

class TestRSIClassifier:
    def test_overbought(self):       assert _classify_rsi(78)  == "overbought"
    def test_approaching_ob(self):   assert _classify_rsi(68)  == "approaching_overbought"
    def test_oversold(self):         assert _classify_rsi(22)  == "oversold"
    def test_approaching_os(self):   assert _classify_rsi(33)  == "approaching_oversold"
    def test_neutral_bullish(self):  assert _classify_rsi(58)  == "neutral_bullish"
    def test_neutral_bearish(self):  assert _classify_rsi(42)  == "neutral_bearish"


class TestMACDClassifier:
    def test_strong_bullish(self):   assert _classify_macd(1.0, 0.0)      == "strong_bullish"
    def test_bullish_cross(self):    assert _classify_macd(0.5, 0.3)      == "bullish_cross"    # ratio=0.25 (boundary)
    def test_weak_bullish(self):     assert _classify_macd(0.103, 0.097)  == "weak_bullish"     # diff=0.006, denom=0.2, ratio=0.03 ∈ (0.01, 0.05)
    def test_flat(self):             assert _classify_macd(0.01, 0.01)    == "flat"              # diff=0, ratio≈0
    def test_weak_bearish(self):     assert _classify_macd(-0.103, -0.097)== "weak_bearish"     # ratio=-0.03 ∈ (-0.05, -0.01)
    def test_bearish_cross(self):    assert _classify_macd(-0.5, -0.3)    == "bearish_cross"    # ratio=-0.25
    def test_strong_bearish(self):   assert _classify_macd(-1.0, 0.0)     == "strong_bearish"


class TestVolumeClassifier:
    def test_strong_bullish(self):   assert _classify_volume(1)   == "strong_bullish"
    def test_bullish(self):          assert _classify_volume(0.5) == "bullish"
    def test_neutral(self):          assert _classify_volume(0)   == "neutral"
    def test_bearish(self):          assert _classify_volume(-0.5)== "bearish"
    def test_strong_bearish(self):   assert _classify_volume(-1)  == "strong_bearish"


class TestStochClassifier:
    def test_overbought(self):       assert _classify_stoch(0.90) == "overbought"
    def test_elevated(self):         assert _classify_stoch(0.72) == "elevated"
    def test_neutral(self):          assert _classify_stoch(0.50) == "neutral"
    def test_depressed(self):        assert _classify_stoch(0.28) == "depressed"
    def test_oversold(self):         assert _classify_stoch(0.10) == "oversold"


class TestVolatilityClassifier:
    def test_extreme(self):          assert _classify_volatility(0.95) == "extreme"
    def test_elevated(self):         assert _classify_volatility(0.75) == "elevated"
    def test_normal(self):           assert _classify_volatility(0.50) == "normal"
    def test_low(self):              assert _classify_volatility(0.10) == "low"


class TestTrendClassifier:
    def test_bullish(self):          assert _classify_trend(1)  == "strong_bullish"
    def test_bearish(self):          assert _classify_trend(-1) == "strong_bearish"
    def test_neutral(self):          assert _classify_trend(0)  == "neutral"


# ── Full Explanation Output Tests ─────────────────────────────────────────────

class TestBuildExplanation:
    """Tests full explanation assembly returns non-empty structured strings."""

    def _call(self, signals, regime, rsi=55, macd=0.1, macd_sig=0.05, stoch=0.5, atr=0.4, conf=0.65):
        return build_explanation(signals, regime, rsi, macd, macd_sig, stoch, atr, conf)

    def test_bullish_trending_returns_nonempty(self):
        text = self._call(ALL_BULLISH, "trending", rsi=55, macd=0.2, macd_sig=0.05)
        assert isinstance(text, str) and len(text) > 50

    def test_bearish_mean_reverting_returns_nonempty(self):
        text = self._call(ALL_BEARISH, "mean_reverting", rsi=25, macd=-0.3, macd_sig=-0.05)
        assert isinstance(text, str) and len(text) > 50

    def test_volatile_regime_mentioned_in_text(self):
        text = self._call(MIXED, "volatile", rsi=65, macd=0.0, macd_sig=0.0)
        assert "VOLATILE" in text.upper() or "volatile" in text.lower(), \
            f"Expected volatile regime mention in: {text[:100]}"

    def test_overbought_rsi_mentioned(self):
        text = self._call(ALL_BULLISH, "trending", rsi=78)
        assert "overbought" in text.lower(), f"Expected 'overbought' in: {text[:150]}"

    def test_oversold_rsi_mentioned(self):
        text = self._call(ALL_BEARISH, "mean_reverting", rsi=22)
        assert "oversold" in text.lower(), f"Expected 'oversold' in: {text[:150]}"

    def test_low_confidence_conclusion_hold(self):
        text = self._call(ALL_NEUTRAL, "random", conf=0.30)
        assert "HOLD" in text.upper(), f"Expected HOLD conclusion: {text[-100:]}"

    def test_high_confidence_bullish_conclusion_buy(self):
        text = self._call(ALL_BULLISH, "trending", conf=0.80)
        assert "BUY" in text.upper() or "bullish" in text.lower(), \
            f"Expected BUY/bullish conclusion: {text[-100:]}"

    def test_all_regimes_produce_output(self):
        for regime in ["trending", "mean_reverting", "volatile", "random"]:
            text = self._call(ALL_BULLISH, regime)
            assert isinstance(text, str) and len(text) > 20, \
                f"Regime '{regime}' produced no explanation"

    def test_no_placeholders_in_output(self):
        """Ensure format strings are resolved (no '{val:.1f}' leaking through)."""
        text = self._call(ALL_BULLISH, "trending", rsi=68, stoch=0.85)
        assert "{val" not in text, f"Unformatted placeholder found in: {text[:150]}"

    def test_output_is_deterministic(self):
        """Same inputs should always produce same output."""
        text1 = self._call(ALL_BULLISH, "trending")
        text2 = self._call(ALL_BULLISH, "trending")
        assert text1 == text2, "Output is not deterministic"


# ── Conclusion Builder Tests ───────────────────────────────────────────────────

class TestConclusion:
    def test_low_confidence_hold(self):
        text = _build_conclusion(ALL_NEUTRAL, 0.30, "random")
        assert "HOLD" in text.upper()

    def test_bullish_alignment_buy(self):
        text = _build_conclusion(ALL_BULLISH, 0.80, "trending")
        assert "BUY" in text.upper() or "bullish" in text.lower()

    def test_bearish_alignment_sell(self):
        text = _build_conclusion(ALL_BEARISH, 0.80, "trending")
        assert "SELL" in text.upper() or "bearish" in text.lower()

    def test_mixed_signals_hold(self):
        mixed = {"trend": 1, "momentum": -1.0, "mean_reversion": 1, "volume": -1, "stoch_rsi": 0}
        text  = _build_conclusion(mixed, 0.50, "random")
        assert "HOLD" in text.upper() or "mixed" in text.lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
