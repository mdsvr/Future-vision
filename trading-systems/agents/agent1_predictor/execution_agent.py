import json
import os
from config import Config
from logger import get_logger

# Optional: Load Alpaca SDK for paper trading execution
try:
    from alpaca_trade_api.rest import REST, APIError
except ImportError:
    REST = None

logger = get_logger()

class ExecutionAgent:
    """
    The final step in the pipeline. Responsible for placing orders on Alpaca.
    This class is 'dumb' by design: it executes based on what main.py instructs.
    """
    def __init__(self, allow_network=False):
        self.allow_network = allow_network
        self.api = None
        
        # Security: Only initialize API if network is explicitly allowed
        if allow_network and REST:
            # We fail silently here if keys are missing (logged later during execute_order)
            self.api = REST(
                key_id=Config.ALPACA_API_KEY,
                secret_key=Config.ALPACA_SECRET_KEY,
                base_url=Config.ALPACA_BASE_URL
            )

    def execute_order(self, symbol, action, allocation_pct, confidence):
        """
        Executes a PAPER trade on Alpaca.
        Primary safety guards are in main.py, but we re-verify network here.
        """
        # 1. Final Network Safety Check
        if not self.allow_network:
            logger.warning(f"Execution BLOCKED: Network disabled for {symbol}.")
            return None

        # 2. API Readiness Check
        if not self.api:
            logger.error(f"Execution FAILED: Alpaca API not initialized. Symbol: {symbol}")
            return None

        # 3. Logic Check
        if action == "HOLD":
            return None

        try:
            logger.info(f"Submitting {action} @ Market for {symbol} | Alloc: {allocation_pct}% | Conf: {confidence}")
            
            # --- Quantity Calculation ---
            # In an MVP, we default to 1 share for safety.
            # Production upgrade path: Query self.api.get_account() to compute qty based on cash balance.
            qty = 1 
            
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=action.lower(),
                type="market",
                time_in_force="gtc" # Good 'til Canceled
            )
            
            logger.info(f"Order Accepted by Alpaca. ID: {order.id}")
            return order.id

        except Exception as e:
            logger.error(f"Alpaca Execution Error for {symbol}: {e}")
            return None
