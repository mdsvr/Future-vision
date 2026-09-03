"""
test_pipeline_smoke.py  —  End-to-End Wiring Check
===================================================
The smallest thing that fails if the pipeline is miswired. Runs entirely on
synthetic candles — no network, no API keys, no pytest.

    py test_pipeline_smoke.py

Covers the failure modes that unit tests on individual modules cannot see:
  1. Every module actually imports (stale module names are the recurring bug here)
  2. Raw OHLCV  → compute_features → main.run  produces a schema-valid prediction
  3. main.run survives being called from inside a running event loop (--fast path)
  4. main.run does not recompute indicators on an already-featured DataFrame
  5. The Guardian's risk-reward rule can actually REJECT a trade
"""

import asyncio
import importlib
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def make_candles(rows: int = 400) -> pd.DataFrame:
    """Deterministic synthetic OHLCV — enough rows to clear the EMA-200 warm-up."""
    idx = pd.date_range("2026-01-01 09:15", periods=rows, freq="15min", tz="UTC")
    rng = np.random.default_rng(7)
    close = 1000 + np.cumsum(rng.normal(0.5, 3, rows))
    df = pd.DataFrame(
        {
            "open":   close + rng.normal(0, 1, rows),
            "high":   close + np.abs(rng.normal(3, 1, rows)),
            "low":    close - np.abs(rng.normal(3, 1, rows)),
            "close":  close,
            "volume": rng.integers(1000, 5000, rows).astype(float),
        },
        index=idx,
    )
    df.index.name = "timestamp"
    return df


def test_every_module_imports():
    """Stale module paths (data_ingestion, indicators, ..confidence) break at import."""
    for name in [
        "config", "logger", "validator", "guardian", "execution_agent",
        "indicator_engine.indicators", "indicator_engine.feature_engine",
        "fusion_engine.confidence", "fusion_engine.regime", "fusion_engine.strategy_engine",
        "fusion_engine.confidence_model", "fusion_engine.regime_detector",
        "reasoning_engine.explanation_builder", "reasoning_engine.llm_reasoner",
        "data_layer.live_market_feed", "data_layer.websocket_client",
        "cache_layer.redis_manager", "async_engine", "main",
    ]:
        importlib.import_module(name)


def test_raw_dataframe_runs_end_to_end():
    """The standard path: raw candles in, schema-valid prediction out."""
    import main

    result = main.run("TEST", mode="SAFE", allow_network=False, precomputed_df=make_candles())
    assert result is not None, "pipeline returned None on valid synthetic data"
    assert result["action"] in ("BUY", "SELL", "HOLD"), result["action"]
    assert 0.0 <= result["confidence"] <= 1.0, result["confidence"]
    # A HOLD that still allocates capital is the contradiction validator.py exists to catch
    if result["action"] == "HOLD":
        assert result["recommended_allocation_pct"] == 0.0


def test_run_survives_inside_a_running_event_loop():
    """--fast calls run() from inside asyncio.run() with an already-featured frame."""
    from indicator_engine.feature_engine import compute_features
    import main

    featured = compute_features(make_candles())   # built outside the loop, as --fast does

    async def inside_loop():
        return main.run("TEST", mode="SAFE", allow_network=False, precomputed_df=featured)

    assert asyncio.run(inside_loop()) is not None


def test_featured_dataframe_is_not_recomputed():
    """An already-enriched frame must pass through untouched, not get a second pass."""
    from indicator_engine.feature_engine import compute_features
    import main

    featured = compute_features(make_candles())
    assert "atr" in featured.columns
    before = len(featured)
    result = main.run("TEST", mode="SAFE", allow_network=False, precomputed_df=featured)
    assert result is not None
    assert len(featured) == before, "input frame was mutated"


def test_guardian_rejects_bad_risk_reward():
    """Rule 4 must be able to fail — it can't when the target is synthesised as entry ± 2R."""
    from guardian import run_guardian_checks

    common = dict(
        action="BUY", confidence=0.90, atr_percentile=0.5,
        allocation=2.0, entry_price=100.0, stop_loss=90.0, atr_val=5.0,
    )
    # Risk 10, reward 5 → RR 0.5, well under the 2.0 minimum
    status, reason, _ = run_guardian_checks(target=105.0, **common)
    assert status == "REJECTED", f"expected REJECTED for 0.5:1 RR, got {status}: {reason}"

    # Risk 10, reward 25 → RR 2.5, comfortably above the minimum
    status, reason, alloc = run_guardian_checks(target=125.0, **common)
    assert status == "APPROVED", f"expected APPROVED for 2.5:1 RR, got {status}: {reason}"
    assert alloc > 0, "approved trade came back with zero allocation"


def test_guardian_rejects_unusable_targets():
    """abs(target - entry) is blind to NaN and to backwards targets — screen them first."""
    from guardian import run_guardian_checks

    common = dict(
        confidence=0.90, atr_percentile=0.5, allocation=2.0,
        entry_price=100.0, stop_loss=90.0, atr_val=5.0,
    )
    for bad in (float("nan"), float("inf"), float("-inf"), "not-a-price", object()):
        status, reason, alloc = run_guardian_checks(action="BUY", target=bad, **common)
        assert status == "REJECTED", f"target={bad!r} gave {status}: {reason}"
        assert alloc == 0.0

    # None is the documented "synthesise a 2R target" path, not a bad target
    status, reason, _ = run_guardian_checks(action="BUY", target=None, **common)
    assert status == "APPROVED", f"synthesised target should pass, got {reason}"

    # Numeric-but-not-float targets coerce rather than crash the comparison
    status, _, _ = run_guardian_checks(action="BUY", target="125", **common)
    assert status == "APPROVED", "numeric string target should coerce and pass"

    # Backwards targets: reward would read as profit because of the abs()
    status, _, _ = run_guardian_checks(action="BUY", target=75.0, **common)
    assert status == "REJECTED", "BUY target below entry should not pass"
    status, _, _ = run_guardian_checks(
        action="SELL", target=125.0,
        **{**common, "stop_loss": 110.0}
    )
    assert status == "REJECTED", "SELL target above entry should not pass"

    # HOLD legitimately carries target == entry and must still pass
    status, _, _ = run_guardian_checks(action="HOLD", target=100.0, **common)
    assert status == "APPROVED", "HOLD must not be caught by the directional check"


def test_guardian_never_returns_negative_allocation():
    """The cap only bounds the top; a sign error must not survive to the caller."""
    from guardian import run_guardian_checks

    _, _, alloc = run_guardian_checks(
        action="BUY", confidence=0.90, atr_percentile=0.5, allocation=-5.0,
        entry_price=100.0, stop_loss=90.0, atr_val=5.0, target=125.0,
    )
    assert alloc == 0.0, f"negative allocation survived as {alloc}"


def test_guardian_caps_oversized_allocation():
    """Rule 3's cap is only real if the caller receives the capped number back."""
    from guardian import run_guardian_checks, _RISK

    cap = _RISK.get("allocation_pct", 10.0)
    _, _, alloc = run_guardian_checks(
        action="BUY", confidence=0.90, atr_percentile=0.5,
        allocation=cap * 50, entry_price=100.0, stop_loss=90.0,
        atr_val=5.0, target=125.0,
    )
    assert alloc == cap, f"allocation {alloc} was not capped to {cap}"


def test_async_pipeline_imports_resolve():
    """run_pipeline_async swallows exceptions, so check its workers directly."""
    from async_engine import _regime_signals_worker
    from indicator_engine.feature_engine import compute_features

    regime, hurst, signals = _regime_signals_worker(compute_features(make_candles()), "TEST")
    assert regime in ("trending", "mean_reverting", "volatile", "random"), regime
    assert 0.0 <= hurst <= 1.0, hurst
    assert set(signals) == {"trend", "momentum", "mean_reversion", "volume", "stoch_rsi"}, signals


if __name__ == "__main__":
    import logging

    logging.getLogger("Agent1").setLevel(logging.CRITICAL)   # keep the output readable
    sys.stdout = open(os.devnull, "w")                       # main.run prints its JSON unconditionally
    report = sys.stderr

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}", file=report)
        except Exception as exc:
            failures += 1
            print(f"FAIL  {test.__name__}: {type(exc).__name__}: {exc}", file=report)

    print(f"\n{len(tests) - failures}/{len(tests)} passed", file=report)
    sys.exit(1 if failures else 0)
