"""
guardian.py  —  The Risk Management Safety Check
=================================================
This is the LAST LINE OF DEFENCE before any trade recommendation goes out.

The Guardian's job is to BLOCK or APPROVE a proposed trade by checking it
against strict safety rules. Think of it as the compliance officer at a bank
— even if the AI says "BUY!", the Guardian must also say "OK".

If ANY rule fails → the trade is BLOCKED and changed to HOLD automatically.

Safety Rules checked:
  1. Confidence Gate     — Must be above the minimum confidence threshold (default 55%)
  2. Stop-Loss Gap       — Stop-loss must be at least 1 ATR away from entry price
  3. Allocation Cap      — Position size must not exceed maximum allowed % of portfolio
  4. Risk-Reward Ratio   — Reward must be at least 2x the risk (2:1 minimum)

Why these 4 rules?
  - Rule 1: Prevents acting on guesses. Low confidence = uncertainty = HOLD.
  - Rule 2: Stop-loss too close = wiped out by normal noise. Needs breathing room.
  - Rule 3: Never go "all-in" on one trade. Limits losses from a single bad call.
  - Rule 4: Classic trading principle. If you risk ₹1, you should expect ₹2 back.

Used by: main.py → called before the prediction is finalised and returned.
"""

import json
import os
from logger import get_logger

logger = get_logger()

# Load risk rules from config.json
# These values can be changed in config.json without touching this code
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(_CONFIG_PATH, "r") as f:
    _raw      = json.load(f)
    _RISK     = _raw["risk"]       # Allocation caps, RR minimums
    _GUARDIAN = _raw["guardian"]   # Confidence threshold, ATR percentile cap


class GuardianAgent:
    """
    The risk management gatekeeper.
    
    Workflow:
        guardian = GuardianAgent()
        status, reason, safe_allocation = guardian.evaluate(
            action, confidence, entry_price, stop_loss, targets, allocation_pct, atr
        )
    
    Returns:
        status         (str):   "APPROVED" or "BLOCKED"
        reason         (str):   Human-readable explanation of the decision
        safe_allocation(float): Approved position size (0.0 if blocked)
    """

    def evaluate(self, action, confidence, entry_price, stop_loss, targets, allocation_pct, atr):
        """
        Runs all safety checks on a proposed trade in sequence.
        The first failing check immediately blocks the trade — no exceptions.

        Args:
            action         (str):   "BUY", "SELL", or "HOLD"
            confidence     (float): AI conviction score (0.0–1.0)
            entry_price    (float): Proposed entry price  (e.g. ₹1394.80)
            stop_loss      (float): Stop-loss price      (e.g. ₹1380.00)
            targets        (list):  Target prices        (e.g. [₹1430.00])
            allocation_pct (float): Proposed % of portfolio to use (e.g. 5.0)
            atr            (float): Average True Range — current volatility measure

        Returns:
            tuple: (status, reason, safe_allocation)
        """

        # ── Rule 0: HOLD always passes ─────────────────────────────────────────
        # HOLD means "do nothing" — no safety concerns, just let it through.
        if action == "HOLD":
            return "APPROVED", "HOLD action allows bypassing risk checks.", 0.0

        # ── Rule 1: Minimum Confidence Gate ───────────────────────────────────
        # If the AI isn't confident enough, block the trade.
        # Default threshold: 0.55 (55%) — set in config.json
        min_conf = _GUARDIAN.get("confidence_threshold", 0.55)
        if confidence < min_conf:
            reason = f"BLOCKED: Confidence {confidence:.2f} below minimum {min_conf:.2f}. Forcing HOLD."
            logger.warning(f"[Guardian] {reason}")
            return "BLOCKED", reason, 0.0

        # ── Rule 2: Stop-Loss Distance Check ──────────────────────────────────
        # Stop-loss must be at least 1 ATR away from entry.
        # If it's too close, normal market swings will trigger it immediately.
        if entry_price > 0 and atr > 0:
            sl_gap = abs(entry_price - stop_loss)
            min_sl_gap = atr * 1.0   # Minimum = 1 ATR (full range of a typical candle)
            if sl_gap < min_sl_gap:
                reason = (
                    f"BLOCKED: Stop-loss gap {sl_gap:.2f} is less than 1 ATR ({atr:.2f}). "
                    f"Too tight — will be triggered by normal market noise."
                )
                logger.warning(f"[Guardian] {reason}")
                return "BLOCKED", reason, 0.0

        # ── Rule 3: Allocation Cap ────────────────────────────────────────────
        # Never put more than the maximum allowed % of the portfolio in one trade.
        # Default cap: 10% — set in config.json
        max_alloc = _RISK.get("allocation_pct", 10.0)
        safe_alloc = min(allocation_pct, max_alloc)
        if allocation_pct > max_alloc:
            logger.warning(
                f"[Guardian] Allocation {allocation_pct}% exceeds cap {max_alloc}%. "
                f"Capped at {safe_alloc}%."
            )

        # ── Rule 4: Risk-Reward Ratio Check ──────────────────────────────────
        # For every ₹1 we risk, we must expect at least ₹2 in reward.
        # This is the classic 2:1 risk-reward rule used by professional traders.
        target_price = targets[0] if targets else entry_price
        risk   = abs(entry_price - stop_loss)
        reward = abs(target_price - entry_price)

        if risk > 0:
            rr_ratio = reward / risk
            min_rr   = _RISK.get("risk_reward_ratio_min", 2.0)
            if rr_ratio < min_rr:
                reason = (
                    f"BLOCKED: Risk-Reward ratio {rr_ratio:.2f} is below minimum {min_rr}. "
                    f"Not enough reward for the risk taken."
                )
                logger.warning(f"[Guardian] {reason}")
                return "BLOCKED", reason, 0.0

        # ── All checks passed ─────────────────────────────────────────────────
        return "APPROVED", "All risk checks passed.", safe_alloc


# ── Backward-compatibility shim ───────────────────────────────────────────────
# main.py does: from guardian import run_guardian_checks
# This function keeps that import working without changing main.py.

def run_guardian_checks(action, confidence, atr_percentile, allocation,
                        entry_price, stop_loss, atr_val=None):
    """
    Backward-compatible wrapper so main.py doesn't need to be modified.

    Args:
        action         (str):   "BUY", "SELL", or "HOLD"
        confidence     (float): AI conviction score (0.0–1.0)
        atr_percentile (float): Percentile rank of current ATR (0–1)
        allocation     (float): Proposed portfolio allocation %
        entry_price    (float): Entry price
        stop_loss      (float): Stop-loss price
        atr_val        (float): OPTIONAL — actual ATR value in price units.
                                If not provided, estimated from atr_percentile.
    """
    guardian = GuardianAgent()

    # Estimate a target price for the RR check (entry ± 2× risk)
    risk   = abs(entry_price - stop_loss) if entry_price != stop_loss else entry_price * 0.01
    target = (entry_price + risk * 2) if action == "BUY" else (entry_price - risk * 2)

    # Use real ATR if provided, otherwise fall back to rough estimate
    # Real ATR is always preferred — the estimate can be inaccurate for volatile symbols
    if atr_val is not None and atr_val > 0:
        atr = atr_val
    else:
        # Fallback: approximate from percentile (1% of price per ATR unit)
        atr = atr_percentile * entry_price * 0.01
        logger.debug(f"[Guardian] Using estimated ATR={atr:.2f} (real ATR not provided)")

    status, reason, _ = guardian.evaluate(
        action=action,
        confidence=confidence,
        entry_price=entry_price,
        stop_loss=stop_loss,
        targets=[target],
        allocation_pct=allocation,
        atr=atr
    )

    # Translate to the old return vocabulary (main.py checks for "REJECTED")
    return ("REJECTED" if status == "BLOCKED" else status), reason
