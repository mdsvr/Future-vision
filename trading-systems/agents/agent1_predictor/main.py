import uuid
import json
import os
import sys
import time
import asyncio
import argparse
from datetime import datetime, timezone

# --- Internal Module Imports ---
from logger import get_logger
from data_ingestion import fetch_ohlcv
from feature_engine import compute_features
from strategy_engine import generate_signals
from confidence import compute_confidence
from regime import classify_regime
from validator import validate_prediction
from guardian import run_guardian_checks
from llm_reasoner import LLMRouter
from execution_agent import ExecutionAgent

# Setup logger for the main process
logger = get_logger()

# Load project configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

def run(symbol, mode="SAFE", allow_network=False):
    """
    Orchestrates the full Agent 1 prediction cycle.
    1. Data Ingestion
    2. Feature Computation
    3. Intelligence Loop (Regime, Signals, Confidence)
    4. Safety & Guardian Validation
    5. Reasoning & Logging
    6. (Optional) Paper Trade Execution
    """
    total_start_time = time.time()
    logger.info(f"--- Launching Agent 1 Prediction Cycle | Symbol: {symbol} | Mode: {mode} | Network: {allow_network} ---")

    # --- Step 0: Initialize Modules ---
    llm_provider = config["intelligence"]["llm_provider"]
    llm_router = LLMRouter(provider=llm_provider, allow_network=allow_network)
    execution_agent = ExecutionAgent(allow_network=allow_network)

    # --- Step 1: Market Data Gathering ---
    if mode == "SAFE":
        # SAFE mode: use yfinance with a short local-compatible pull (no --allow-network needed)
        # We force allow_network=True just for data fetch in SAFE mode (yfinance only)
        logger.info("[SAFE] Loading data using yfinance (read-only, no trades will execute).")
        df = fetch_ohlcv(symbol)
    elif not allow_network:
        logger.error(f"[Safety] Network blocked for mode {mode}. Add --allow-network flag to proceed.")
        return
    else:
        df = fetch_ohlcv(symbol)

    if df is None:
        logger.error("[Error] Aborting cycle: Market data fetch failed.")
        return

    # --- Step 2: Feature Engineering & Indicators ---
    logger.info("[Process] Computing technical indicators (EMA, MACD, RSI, OBV, ATR)...")
    df = compute_features(df)

    # Guard: compute_features may return an empty DataFrame if the data is too short
    # or all-zero volume (e.g. index symbols during warm-up). Abort cleanly.
    if df is None or len(df) == 0:
        logger.error("[Error] Aborting cycle: DataFrame empty after feature computation. Not enough valid data.")
        return None

    # --- Step 3: Intelligence & Regime Detection ---
    # Determine the current market 'vibe' (Trending vs Mean Reverting)
    regime, hurst_value = classify_regime(df)
    logger.info(f"[Intelligence] Market Context: {regime} (Hurst: {hurst_value})")

    # Generate signals based on the detected regime
    signals = generate_signals(df, regime)
    logger.info(f"[Signals] Technical Signals: {signals}")

    # Determine volatility context (ATR Percentile)
    atr_series = df['atr']
    atr_percentile = float(atr_series.rank(pct=True).iloc[-1])
    logger.info(f"[Analysis] Volatility Context: ATR Percentile is {atr_percentile:.3f}")

    # Calculate overall signal confidence
    confidence = compute_confidence(signals, regime, atr_percentile)
    logger.info(f"[Confidence] Score: {confidence:.3f}")

    # --- Step 4: Primary Strategy Decision ---
    # First pass: Choose action based on net indicators
    if confidence < config["guardian"]["confidence_threshold"]:
        # If indicators are muddy or confidence is low, we always HOLD
        action = "HOLD"
        allocation = 0.0
    else:
        # Sum signals (e.g. +1 Trend, +0.5 Momentum = 1.5 total score)
        direction_score = sum(signals.values())
        action = "BUY" if direction_score > 0 else "SELL" if direction_score < 0 else "HOLD"
        allocation = config["risk"]["allocation_pct"] if action != "HOLD" else 0.0

    # --- Step 5: Risk Level Computation (Stops/Targets) ---
    latest_bar = df.iloc[-1]
    entry_price = float(latest_bar['close'])
    atr_val = float(latest_bar['atr'])

    # Multiplier-based stops (config-driven)
    stop_dist = config["risk"]["stop_loss_atr_multiplier"] * atr_val
    target_dist = config["risk"]["target_atr_multiplier"] * atr_val

    if action == "BUY":
        stop_loss = entry_price - stop_dist
        target = entry_price + target_dist
    elif action == "SELL":
        stop_loss = entry_price + stop_dist
        target = entry_price - target_dist
    else:
        # Defaults for HOLD
        stop_loss = entry_price
        target = entry_price
        
    logger.info(f"[Strategy] Proposal: {action} @ {entry_price:.2f} | Stop: {stop_loss:.2f}")

    # --- Step 6: The Guardian (Final Safety Gate) ---
    # Guardian checks risk levels, volatility, and confidence before approving a trade
    status, reason = run_guardian_checks(
        action=action,
        confidence=confidence,
        atr_percentile=atr_percentile,
        allocation=allocation,
        entry_price=entry_price,
        stop_loss=stop_loss,
        atr_val=atr_val           # Pass real ATR (not approximated from percentile)
    )
    logger.info(f"[Guardian] Gatekeeper -> Status: {status} | Reason: {reason}")
    
    if status == "REJECTED":
        action = "HOLD"
        allocation = 0.0
        logger.info("[Guardian] Vetoed the trade. Reverting to HOLD.")

    # --- Step 7: Descriptive Reasoning (LLM or Fallback) ---
    # Pass raw indicator values so explanation_builder produces per-indicator narratives
    latest_indicators = df.iloc[-1]
    raw_indicators = {
        "rsi":          float(latest_indicators.get('rsi',          50.0)),
        "macd":         float(latest_indicators.get('macd',         0.0)),
        "macd_signal":  float(latest_indicators.get('macd_signal',  0.0)),
        "stoch_rsi":    float(latest_indicators.get('stoch_rsi',    0.5)),
    }
    reasoning_text = llm_router.generate_reasoning(
        symbol         = symbol,
        regime         = regime,
        signals        = signals,
        confidence     = confidence,
        atr_percentile = atr_percentile,
        raw_indicators = raw_indicators,
    )

    # --- Step 8: Build Validated Prediction Object ---
    # This JSON object follows the standardized Agent 1 schema
    prediction = {
        "schema_version": "1.0",
        "prediction_id": str(uuid.uuid4()),
        "symbol": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "confidence": confidence,
        "recommended_allocation_pct": allocation,
        "time_horizon": "intraday",
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "targets": [target],
        "risk_reward_ratio": config["risk"]["target_atr_multiplier"] / config["risk"]["stop_loss_atr_multiplier"],
        "indicators_used": [
            "EMA_200", "EMA_50",        # Trend
            "RSI", "MACD", "StochRSI",  # Momentum
            "ATR", "BollingerBands",    # Volatility
            "OBV", "VWAP",              # Volume / Fair value
        ],
        "patterns_detected": [],
        "strategy_signals": signals,
        "market_regime": f"{regime}_H{hurst_value}",
        "reasoning": reasoning_text,
        "guardian_status": status,
        "guardian_reason": reason,
        "provenance": {
            "run_id": str(uuid.uuid4()),
            "model": "deterministic_engine_v3",
            "data_sources": [config["data"]["market_data_provider"]]
        },
        "metadata": {
            "mode": mode,
            "network_allowed": allow_network,
            "llm_provider": llm_provider
        }
    }

    # Internal Validation against JSON Schema and domain rules
    is_valid, validation_msg = validate_prediction(prediction)
    if not is_valid:
        logger.error(f"[Validation] Output validation failed: {validation_msg}")
        return

    # --- Step 9: Execution (Only in PAPER mode) ---
    order_id = None
    if mode == "PAPER":
        if not allow_network:
            logger.error("[Execution] Network required for PAPER trades. Execution skipped.")
        elif status == "APPROVED" and action != "HOLD":
            logger.info(f"[Execution] Paper Trade Triggered: {action} {symbol}")
            order_id = execution_agent.execute_order(
                symbol=symbol,
                action=action,
                allocation_pct=allocation,
                confidence=confidence
            )
        else:
            logger.info("[Execution] Trade execution skipped (either HOLD or Guardian REJECTED).")

    if order_id:
        prediction["order_id"] = order_id

    # Performance logging
    final_cycle_time = int((time.time() - total_start_time) * 1000)
    logger.info(f"[Success] Prediction Cycle Completed in {final_cycle_time}ms")
    
    # Final structured output to stdout
    print(json.dumps(prediction, indent=2))
    return prediction

# --- Main CLI Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 1 Trading Predictor (Integrated API Prototype)")

    # Environment Controls
    parser.add_argument("--mode", type=str, choices=["SAFE", "LIVE_DATA", "PAPER"], default="SAFE",
                        help="Operating mode. PAPER triggers execution.")
    parser.add_argument("--allow-network", action="store_true",
                        help="Allow external connections for Data and LLM access.")

    # Performance Controls
    parser.add_argument("--fast", action="store_true",
                        help="Use async_engine parallel pipeline for faster execution.")

    # Overrides
    parser.add_argument("--symbol", type=str,
                        help="Ticker to analyze (e.g. AAPL, BTC-USD). Overrides config.json")

    args = parser.parse_args()

    # Resolve symbol priority (CLI override > Config file)
    target_symbol = args.symbol if args.symbol else config["data"]["symbol"]

    if args.fast:
        # ── Fast async path ────────────────────────────────────────────────
        # Runs data fetch + feature computation in async thread pool
        # then hands off to the standard confidence/guardian/reasoning flow
        from async_engine import run_pipeline_async

        async def _fast_run():
            logger.info(f"[FastMode] Async pipeline starting for {target_symbol}")
            result = await run_pipeline_async(target_symbol)
            if result is None:
                logger.error("[FastMode] Async pipeline returned no result. Aborting.")
                sys.exit(1)
            # Re-enter the standard pipeline from Step 3 onwards
            run(target_symbol, mode=args.mode, allow_network=args.allow_network)

        asyncio.run(_fast_run())
    else:
        # ── Standard synchronous path ──────────────────────────────────────
        run(target_symbol, mode=args.mode, allow_network=args.allow_network)