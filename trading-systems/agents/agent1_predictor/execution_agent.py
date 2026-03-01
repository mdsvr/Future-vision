"""
execution_agent.py  —  Paper Trade Order Execution
====================================================
The FINAL step in the agent pipeline. Takes the approved prediction
from main.py and places a paper trade order on Alpaca.

WHAT IS PAPER TRADING?
  Paper trading = simulated trading with fake money.
  Alpaca's paper trading API works identically to real trading,
  but no real money changes hands. It's safe for testing strategies.

THIS MODULE IS CURRENTLY IN STANDBY MODE.
  The agent currently uses Fyers for Indian stocks and does NOT
  place live or paper trades automatically. This class is designed
  for FUTURE activation when automated execution is needed.

SAFETY DESIGN:
  - The class requires 'allow_network=True' to even initialize.
  - HOLD actions are silently ignored (no order placed).
  - All orders default to 1 share (conservative start).
  - All errors are logged but never crash the main pipeline.

To activate in the future:
  1. Set Alpaca paper trading keys in .env
  2. Set 'allow_network=True' when calling ExecutionAgent()
  3. Adjust qty calculation to use real portfolio balance

Used by: main.py (currently disabled; reserved for future use)
"""

import json
import os
from config import Config
from logger import get_logger

# ── Try to import Alpaca SDK ──────────────────────────────────────────────────
# Alpaca is optional — if not installed, execution is silently disabled.
# Install with: pip install alpaca-trade-api
try:
    from alpaca_trade_api.rest import REST, APIError
except ImportError:
    REST = None    # Execution will be silently skipped if library is missing

logger = get_logger()


class ExecutionAgent:
    """
    Places paper trade orders on Alpaca based on the agent's prediction.

    Safety hierarchy:
        1. network must be explicitly enabled
        2. Alpaca SDK must be installed
        3. API keys must be valid
        4. Action must be BUY or SELL (HOLD = skip)
        5. All exceptions are caught and logged (never crash the pipeline)
    """

    def __init__(self, allow_network: bool = False):
        """
        Initializes the Alpaca connection.

        Args:
            allow_network (bool): Must be True to allow any network calls.
                                  Default is False for safety.
        """
        self.allow_network = allow_network
        self.api = None

        # Only initialize the trading connection if network access is explicitly allowed
        # AND the Alpaca library is installed
        if allow_network and REST:
            self.api = REST(
                key_id=Config.ALPACA_API_KEY,
                secret_key=Config.ALPACA_SECRET_KEY,
                base_url=Config.ALPACA_BASE_URL    # Points to paper trading URL by default
            )

    def execute_order(self, symbol: str, action: str, allocation_pct: float, confidence: float):
        """
        Submits a paper trade order to Alpaca.

        Args:
            symbol         (str):   Stock ticker, e.g. "AAPL"
            action         (str):   "BUY", "SELL", or "HOLD"
            allocation_pct (float): % of portfolio to use (e.g. 5.0 = 5%)
            confidence     (float): AI confidence score used for logging

        Returns:
            str or None: Alpaca order ID if successful, None if skipped/failed.
        """

        # ── Safety Check 1: Network must be enabled ───────────────────────────
        if not self.allow_network:
            logger.warning(f"Execution BLOCKED: Network disabled for {symbol}.")
            return None

        # ── Safety Check 2: Alpaca API must be initialized ────────────────────
        if not self.api:
            logger.error(f"Execution FAILED: Alpaca API not initialized. Symbol: {symbol}")
            return None

        # ── Safety Check 3: Don't act on HOLD ────────────────────────────────
        # HOLD = "do nothing" — no order should ever be placed for a HOLD recommendation
        if action == "HOLD":
            return None

        try:
            logger.info(
                f"Submitting {action} @ Market for {symbol} | "
                f"Alloc: {allocation_pct}% | Conf: {confidence}"
            )

            # ── Quantity Calculation ──────────────────────────────────────────
            # Currently defaults to 1 share per trade (conservative and safe for testing).
            #
            # Future upgrade path:
            #   account  = self.api.get_account()
            #   cash     = float(account.cash)
            #   price    = self.api.get_latest_trade(symbol).price
            #   qty      = int((cash * allocation_pct / 100) / price)
            qty = 1

            # ── Place the order ───────────────────────────────────────────────
            # time_in_force="gtc" = "Good Till Cancelled"
            # This means the order stays open until filled or manually cancelled.
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=action.lower(),   # "buy" or "sell" (Alpaca uses lowercase)
                type="market",         # Market order = fill at current best price
                time_in_force="gtc"
            )

            logger.info(f"Order Accepted by Alpaca. ID: {order.id}")
            return order.id

        except Exception as e:
            # Catch ALL errors — execution failures should never crash the agent
            logger.error(f"Alpaca Execution Error for {symbol}: {e}")
            return None
