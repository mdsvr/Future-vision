import json
import os

# Load safety thresholds (confidence, max loss, etc.)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

def run_guardian_checks(action, confidence, atr_percentile, allocation, entry_price, stop_loss):
    """
    The Safety Gatekeeper. 
    Reviews every proposed trade against hard risk limits.
    Returns: (status, reason)
    """
    g_config = config["guardian"]
    r_config = config["risk"]

    # 🕊️ Special Case: Neutral actions bypass risk checks
    if action == "HOLD":
        return "APPROVED", "HOLD action allows bypassing risk checks."

    # 1. Conviction Check
    # Avoid taking trades where indicators are mixed or weak.
    if confidence < g_config["confidence_threshold"]:
        return "REJECTED", f"Confidence ({confidence}) below minimum threshold ({g_config['confidence_threshold']})"

    # 2. Market Stability Check (ATR Percentile)
    # Avoid trading during 'black swan' volatility spikes or massive news events.
    if atr_percentile > g_config["atr_percentile_max"]:
        return "REJECTED", f"Volatility ({atr_percentile:.3f}) exceeds safety limit ({g_config['atr_percentile_max']})"

    # 3. Size Compliance check
    # Ensures the strategy engine isn't trying to bet the whole farm.
    if allocation > r_config["allocation_pct"]:
        return "REJECTED", f"Allocation ({allocation}%) violates max size limit ({r_config['allocation_pct']}%)"

    # 4. Stop Loss 'Tightness' check
    # Stops that are too close to current price (<0.1%) often get hit by random spread noise.
    distance_pct = abs(entry_price - stop_loss) / entry_price * 100
    if distance_pct < 0.1: 
        return "REJECTED", f"Stop loss distance ({distance_pct:.2f}%) is too narrow for spread noise."
        
    # 5. Portfolio Hit Simulation
    # Calculates the 'Real Risk' (RR): How much of the TOTAL CAPITAL is lost if this trade hits STOP.
    # Formula: Allocation % * Stop Loss % distance (Simplified un-leveraged model).
    portfolio_hit_pct = allocation * (distance_pct / 100) 
    
    # We compare this against the 'Max Daily Loss' limit from config.
    if portfolio_hit_pct > abs(r_config["max_daily_loss_pct"]):
         return "REJECTED", f"Trade risk ({portfolio_hit_pct:.2f}%) exceeds daily max loss limit."

    return "APPROVED", "All checks passed successfully."
