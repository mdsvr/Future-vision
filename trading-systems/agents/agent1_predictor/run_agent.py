"""
run_agent.py  —  Agent 1 Interactive Launcher
=============================================
Run this file instead of main.py for an easy, guided experience.
It will ask you which market and which stock to analyse,
then show the result in plain English that anyone can understand.

Usage:
    py run_agent.py
"""

import os
import sys
import json

# ─────────────────────────────────────────────────────────────
#  COLOUR HELPERS  (works on Windows 10+ and all modern terminals)
# ─────────────────────────────────────────────────────────────
try:
    import colorama
    colorama.init(autoreset=True)
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
except ImportError:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def banner():
    print()
    print(BOLD + CYAN + "=" * 56)
    print("        AGENT 1  —  AI Stock Analyser")
    print("=" * 56 + RESET)
    print()

def hr():
    print(CYAN + "-" * 56 + RESET)

def ask(prompt, options=None):
    """Ask a question and return the user's answer (validated against options if provided)."""
    while True:
        raw = input(BOLD + prompt + RESET + " ").strip()
        if not options:
            return raw
        if raw.upper() in [o.upper() for o in options]:
            return raw.upper()
        print(f"{YELLOW}  Please enter one of: {', '.join(options)}{RESET}")


# ─────────────────────────────────────────────────────────────
#  MARKET SELECTION
# ─────────────────────────────────────────────────────────────

def select_market():
    """Ask the user whether they want US or Indian stocks."""
    hr()
    print(BOLD + "  Step 1 of 3 — Choose Your Market" + RESET)
    hr()
    print()
    print("  1.  US Stocks    (Apple, Tesla, Google, NVIDIA, etc.)")
    print("  2.  India Stocks (Reliance, TCS, Infosys, HDFC, etc.)")
    print()

    choice = ask("  Enter 1 for US  or  2 for India:", options=["1", "2"])

    if choice == "1":
        return "US"
    else:
        return "INDIA"


# ─────────────────────────────────────────────────────────────
#  SYMBOL SELECTION
# ─────────────────────────────────────────────────────────────

US_EXAMPLES = {
    "AAPL":  "Apple Inc.",
    "TSLA":  "Tesla Inc.",
    "NVDA":  "NVIDIA Corp.",
    "MSFT":  "Microsoft Corp.",
    "GOOGL": "Alphabet (Google)",
    "AMZN":  "Amazon",
    "META":  "Meta (Facebook)",
}

INDIA_EXAMPLES = {
    "RELIANCE":   "Reliance Industries",
    "TCS":        "Tata Consultancy Services",
    "INFY":       "Infosys",
    "HDFCBANK":   "HDFC Bank",
    "ITC":        "ITC Ltd.",
    "WIPRO":      "Wipro",
    "SBIN":       "State Bank of India",
    "TATAMOTORS": "Tata Motors",
    "BAJFINANCE": "Bajaj Finance",
}

def select_symbol(market):
    """Ask the user to pick or type a stock symbol."""
    hr()
    print(BOLD + "  Step 2 of 3 — Choose a Stock" + RESET)
    hr()

    if market == "US":
        examples = US_EXAMPLES
    else:
        examples = INDIA_EXAMPLES

    print()
    print("  Popular choices:")
    for sym, name in examples.items():
        print(f"    {CYAN}{sym:<25}{RESET} {name}")
    print()

    # Strip spaces and normalise input (e.g. "nifty 50" → "NIFTY50", "nifity" → handled below)
    symbol = input(BOLD + f"  Type a stock name (e.g. RELIANCE, TCS, INFY): " + RESET)
    symbol = symbol.strip().upper().replace(" ", "")  # Remove all spaces
    if not symbol:
        symbol = list(examples.keys())[0]
        print(f"  No input — using default: {symbol}")

    # Strip any prefix/suffix if user typed full Fyers format — extract clean ticker
    if ":" in symbol:
        symbol = symbol.split(":")[-1].replace("-EQ", "").replace("-BE", "").replace("-INDEX", "")
        print(f"  Using ticker: {CYAN}{symbol}{RESET}")

    # ── NSE symbol aliases / corrections ─────────────────────────
    # Fyers requires exact NSE ticker codes — fix common shortcuts.
    # Indices use a special key prefix "IDX:" so the symbol builder knows
    # to format them as NSE:NIFTY50-INDEX instead of NSE:NIFTY50-EQ.
    NSE_ALIASES = {
        # ── INDICES ── (use IDX: prefix to signal -INDEX suffix needed)
        "NIFTY50":       "IDX:NIFTY50",
        "NIFTY":         "IDX:NIFTY50",
        "NIFTY50INDEX":  "IDX:NIFTY50",
        "NIFTYFIFTY":    "IDX:NIFTY50",
        "BANKNIFTY":     "IDX:NIFTYBANK",
        "NIFTYBANK":     "IDX:NIFTYBANK",
        "BANKINDEX":     "IDX:NIFTYBANK",
        "FINNIFTY":      "IDX:FINNIFTY",
        "NIFTYFIN":      "IDX:FINNIFTY",
        "MIDCAPNIFTY":   "IDX:NIFTYMIDCAP50",
        "MIDCPNIFTY":    "IDX:NIFTYMIDCAP50",
        "NIFTYNEXT50":   "IDX:NIFTYNXT50",
        "NIFTYNXT50":    "IDX:NIFTYNXT50",
        "SENSEX":        "IDX:BSE:SENSEX",    # BSE:SENSEX-INDEX, NOT NSE
        "BSE500":        "IDX:BSE:BSE500-INDEX",
        # India VIX — computed index, volume is always zero
        "INDIAVIX":      "IDX:NSE:INDIAVIX",
        "INDIA_VIX":     "IDX:NSE:INDIAVIX",
        "VIX":           "IDX:NSE:INDIAVIX",
        "INDVIX":        "IDX:NSE:INDIAVIX",
        # ── EQUITIES ── (typo corrections + common shortcuts)
        # HDFC merger: HDFC Ltd merged into HDFC Bank in 2023
        "HDFC":          "HDFCBANK",
        # Tata companies
        "TATA":          "TATAMOTORS",
        "TATAMOTOR":     "TATAMOTORS",
        # SBI
        "SBI":           "SBIN",
        "STATEBANK":     "SBIN",
        # Bajaj
        "BAJAJ":         "BAJFINANCE",
        "BAJAJFIN":      "BAJFINANCE",
        # Adani
        "ADANI":         "ADANIENT",
        # Kotak
        "KOTAK":         "KOTAKBANK",
        # Axis
        "AXIS":          "AXISBANK",
        # ICICI
        "ICICI":         "ICICIBANK",
        # Larsen & Toubro
        "LT":            "LT",
        "LARSEN":        "LT",
        # HUL
        "HUL":           "HINDUNILVR",
        "UNILEVER":      "HINDUNILVR",
        # M&M
        "MM":            "M&M",
        "MAHINDRA":      "M&M",
        # Maruti
        "MARUTI":        "MARUTI",
        "SUZUKI":        "MARUTI",
        # Others
        "HERO":          "HEROMOTOCO",
        "BAJAJATO":      "BAJAJ-AUTO",
        "SUNPHARMA":     "SUNPHARMA",
        "DRREDDY":       "DRREDDY",
        "CIPLA":         "CIPLA",
        "BHARTIAIRTEL":  "BHARTIAIRTEL",
        "AIRTEL":        "BHARTIAIRTEL",
        "JIOFINANCE":    "JIOFIN",
        "ZOMATO":        "ZOMATO",
        "PAYTM":         "PAYTM",
        # ── Typo corrections ──
        "NIFITY50":      "IDX:NIFTY50",    # typo: nifity
        "NIFFTY50":      "IDX:NIFTY50",    # typo: niffty
        "NIFTY5O":       "IDX:NIFTY50",    # typo: 5O vs 50
        "RELAINCE":      "RELIANCE",        # common typo
        "RELINACE":      "RELIANCE",
        "INOFOSYS":      "INFY",
        "INFOSYS":       "INFY",
        "TATAMOTORS":    "TATAMOTORS",
    }

    if market == "INDIA" and symbol in NSE_ALIASES:
        corrected = NSE_ALIASES[symbol]
        original  = symbol
        # Strip the IDX: internal marker to show user the clean name
        display_corrected = corrected.replace("IDX:", "")
        if display_corrected != symbol:
            print(f"  {YELLOW}Note: '{original}' → using '{display_corrected}'{RESET}")
        symbol = corrected   # Keep IDX: prefix so symbol builder below knows the suffix

    # ── Smart cross-market check ──────────────────────────────
    # US stocks / names that users commonly type by mistake in India mode
    US_NAMES = {
        "APPLE": "AAPL", "AAPL": "AAPL",
        "TESLA": "TSLA", "TSLA": "TSLA",
        "GOOGLE": "GOOGL", "GOOGL": "GOOGL", "ALPHABET": "GOOGL",
        "MICROSOFT": "MSFT", "MSFT": "MSFT",
        "AMAZON": "AMZN", "AMZN": "AMZN",
        "META": "META", "FACEBOOK": "META",
        "NVIDIA": "NVDA", "NVDA": "NVDA",
        "NETFLIX": "NFLX", "NFLX": "NFLX",
        "AMD": "AMD", "INTEL": "INTC", "INTC": "INTC",
    }

    if market == "INDIA" and symbol in US_NAMES:
        us_ticker = US_NAMES[symbol]
        print()
        print(YELLOW + f"  ⚠  '{symbol}' is a US stock (ticker: {us_ticker}), not an Indian NSE stock." + RESET)
        print(f"  NSE doesn't have {symbol}. What would you like to do?")
        print()
        print(f"  1. Switch to US market and analyse {us_ticker}")
        print(f"  2. Type a different Indian stock name")
        print()
        choice = ask("  Enter 1 or 2:", options=["1", "2"])
        if choice == "1":
            # Return a special signal to switch market
            return "__SWITCH_US__", us_ticker
        else:
            return select_symbol(market)  # Ask again

    return symbol


# ─────────────────────────────────────────────────────────────
#  CONFIRMATION
# ─────────────────────────────────────────────────────────────

def confirm(market, symbol):
    """Show a summary and ask for final confirmation."""
    hr()
    print(BOLD + "  Step 3 of 3 — Confirm & Run" + RESET)
    hr()
    print()
    # Strip any internal IDX: or exchange prefix for clean display
    display = symbol.split(":")[-1].replace("-EQ","").replace("-INDEX","").replace("IDX:","")
    print(f"  Market  :  {BOLD}{market} Stocks{RESET}")
    print(f"  Symbol  :  {BOLD}{CYAN}{display}{RESET}")
    print()
    print("  The agent will:")
    print("    • Fetch the latest market data")
    print("    • Run AI technical analysis")
    print("    • Give you a BUY / SELL / HOLD recommendation")
    print()

    go = ask("  Ready? (Y to continue, N to restart):", options=["Y", "N"])
    return go == "Y"


# ─────────────────────────────────────────────────────────────
#  CONFIG PATCHER  —  temporarily switch provider without editing config.json
# ─────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def patch_config(market, run_symbol):
    """
    Update config.json to reflect selected market, provider and resolved symbol.

    Args:
        market     (str): "INDIA" or "US"
        run_symbol (str): Fully resolved Fyers/yfinance symbol, e.g. 'NSE:RELIANCE-EQ'
                          or 'NSE:INDIAVIX-INDEX' or 'AAPL'.
                          This is written directly to config so it is never corrupted.
    """
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)

    cfg["data"]["symbol"] = run_symbol   # Always write the fully resolved symbol

    if market == "INDIA":
        cfg["data"]["market_data_provider"] = "fyers"
        cfg["data"]["interval"] = "15m"
        cfg["data"]["period"]   = "15d"
    else:
        cfg["data"]["market_data_provider"] = "yfinance"
        cfg["data"]["interval"] = "5m"
        cfg["data"]["period"]   = "15d"

    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ─────────────────────────────────────────────────────────────
#  FRIENDLY OUTPUT PRINTER
# ─────────────────────────────────────────────────────────────

def friendly_output(result, symbol, market="US"):
    """
    Convert the raw prediction dict into plain English.
    """
    currency = "₹" if market == "INDIA" else "$"
    if result is None:
        print(RED + "\n  Something went wrong. Please check the logs.\n" + RESET)
        return

    action     = result.get("action", "HOLD")
    confidence = result.get("confidence", 0.0)
    entry      = result.get("entry_price", 0.0)
    stop       = result.get("stop_loss", 0.0)
    targets    = result.get("targets", [entry])
    regime     = result.get("market_regime", "unknown")
    reasoning  = result.get("reasoning", "")
    guardian   = result.get("guardian_status", "APPROVED")
    alloc      = result.get("recommended_allocation_pct", 0.0)
    signals    = result.get("strategy_signals", {})

    # --- Confidence label ---
    conf_pct = int(confidence * 100)
    if conf_pct >= 75:
        conf_label = "VERY HIGH"
        conf_color = GREEN
    elif conf_pct >= 55:
        conf_label = "MODERATE"
        conf_color = YELLOW
    else:
        conf_label = "LOW"
        conf_color = RED

    # --- Action label ---
    if action == "BUY":
        action_banner = GREEN + BOLD + "  RECOMMENDATION:  BUY  (Go Long)" + RESET
        action_explain = "The AI thinks this is a GOOD time to BUY this stock."
    elif action == "SELL":
        action_banner = RED + BOLD + "  RECOMMENDATION:  SELL  (Exit / Short)" + RESET
        action_explain = "The AI thinks this is a GOOD time to SELL or EXIT this stock."
    else:
        action_banner = YELLOW + BOLD + "  RECOMMENDATION:  HOLD  (Wait & Watch)" + RESET
        action_explain = "The AI is NOT confident enough to buy or sell right now. Best to WAIT."

    # --- Market trend reading ---
    trend    = signals.get("trend", 0)
    momentum = signals.get("momentum", 0)

    if trend > 0 and momentum > 0:
        trend_desc = "The stock is going UP. Prices are rising and buyers are in control."
    elif trend < 0 and momentum < 0:
        trend_desc = "The stock is going DOWN. Sellers are in control right now."
    elif trend == 0 and momentum == 0:
        trend_desc = "The stock is moving SIDEWAYS. No clear direction yet."
    else:
        trend_desc = "The market is MIXED — conflicting signals. The AI is being careful."

    # --- Risk explain ---
    if entry > 0 and stop > 0:
        risk_amount = abs(entry - stop)
        risk_pct    = (risk_amount / entry) * 100
        risk_desc   = (
            f"If things go wrong, the safety stop-loss is at ${stop:.2f} — "
            f"that's a {risk_pct:.1f}% risk from entry."
        )
    else:
        risk_desc = "No specific risk level calculated (HOLD mode)."

    target_price = targets[0] if targets else entry
    if target_price > entry:
        reward_desc = f"Target price if BUY succeeds: ${target_price:.2f}"
    else:
        reward_desc = ""

    # ── PRINT THE REPORT ──────────────────────────────────────
    print()
    print(BOLD + CYAN + "=" * 56)
    print(f"      ANALYSIS REPORT  —  {symbol}")
    print("=" * 56 + RESET)
    print()
    print(action_banner)
    print()
    print(f"  {action_explain}")
    print()
    hr()
    print(BOLD + "  HOW CONFIDENT IS THE AI?" + RESET)
    print(f"    {conf_color}{conf_pct}% confident  ({conf_label}){RESET}")
    print(f"    (Below 55% = not confident enough → HOLD is forced for safety)")
    print()
    hr()
    print(BOLD + "  WHAT IS THE MARKET DOING?" + RESET)
    print(f"    {trend_desc}")
    print()
    hr()
    print(BOLD + "  PRICE DETAILS" + RESET)
    print(f"    Current Price  :  {currency}{entry:.2f}")
    if action == "BUY":
        print(f"    Stop Loss      :  {currency}{stop:.2f}  (automatic protection)")
        print(f"    {reward_desc}")
        print(f"    Money at risk  :  {risk_desc}")
    print()
    hr()
    print(BOLD + "  AI EXPLANATION" + RESET)
    # Wrap long reasoning text at 50 chars
    words = reasoning.replace("\n", " ").split()
    line = "    "
    for word in words:
        if len(line) + len(word) > 54:
            print(line)
            line = "    " + word + " "
        else:
            line += word + " "
    if line.strip():
        print(line)
    print()
    hr()
    print(BOLD + "  SAFETY CHECK  (Guardian)" + RESET)
    if guardian == "APPROVED":
        print(f"    {GREEN}PASSED{RESET}  — The safety system approved this analysis.")
    else:
        print(f"    {RED}BLOCKED{RESET}  — The safety system stopped this trade. Too risky.")
    print()
    if alloc > 0:
        print(f"  Suggested position size: {alloc:.1f}% of your portfolio")
        print()
    print(BOLD + CYAN + "=" * 56 + RESET)
    print()

    # Simple one-liner summary
    print(BOLD + "  SUMMARY IN ONE LINE:" + RESET)
    if action == "BUY":
        print(f"  {GREEN}Buy {symbol} now at {currency}{entry:.2f}. Stop loss at {currency}{stop:.2f}. AI is {conf_pct}% confident.{RESET}")
    elif action == "SELL":
        print(f"  {RED}Exit / Sell {symbol} now (AI is {conf_pct}% confident in this direction).{RESET}")
    else:
        print(f"  {YELLOW}Don't buy or sell {symbol} right now. Confidence too low ({conf_pct}%). Wait.{RESET}")
    print()


# ─────────────────────────────────────────────────────────────
#  MAIN FLOW
# ─────────────────────────────────────────────────────────────

def main():
    sys.path.insert(0, os.path.dirname(__file__))

    banner()

    while True:
        market = select_market()
        print()
        result_sym = select_symbol(market)
        print()

        # Handle cross-market switch (e.g. user types "APPLE" in India mode)
        if isinstance(result_sym, tuple) and result_sym[0] == "__SWITCH_US__":
            market = "US"
            symbol = result_sym[1]
            print(f"  {GREEN}Switched to US market. Analysing {symbol}.{RESET}\n")
        else:
            symbol = result_sym

        if confirm(market, symbol):
            break
        print(f"\n{YELLOW}  Restarting...\n{RESET}")

    # For India: Fyers token is required — no fallback
    if market == "INDIA":
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
        token = os.getenv("FYERS_ACCESS_TOKEN", "")
        if not token or token == "your_fyers_access_token":
            print()
            print(RED + BOLD + "  ! Fyers Login Required for Indian Stocks" + RESET)
            print()
            print("  Run this to log in (takes about 1 minute):")
            print()
            print(CYAN + "      py fyers_mcp_auth.py" + RESET)
            print()
            print("  It opens Fyers login, saves your token, and verifies it.")
            print("  Then come back and run:  py run_agent.py")
            print()
            return

    # Compute the actual Fyers-format symbol to pass to the engine
    if market == "INDIA":
        if symbol.startswith("IDX:"):
            # Index symbol — format is IDX:[EXCHANGE:]TICKER
            # e.g. IDX:NSE:INDIAVIX → NSE:INDIAVIX-INDEX
            # e.g. IDX:BSE:SENSEX   → BSE:SENSEX-INDEX
            # e.g. IDX:NIFTY50     → NSE:NIFTY50-INDEX (default to NSE)
            inner = symbol[4:]   # Strip "IDX:"
            if ":" in inner:
                # Exchange explicitly embedded — use it as-is + -INDEX suffix
                run_symbol = f"{inner}-INDEX"
            else:
                # No exchange specified — default to NSE
                run_symbol = f"NSE:{inner}-INDEX"
        else:
            # Regular equity — uses -EQ suffix (e.g. NSE:RELIANCE-EQ)
            run_symbol = f"NSE:{symbol}-EQ"
    else:
        run_symbol = symbol               # e.g. AAPL

    # Friendly display name (no NSE:/BSE: prefix, no suffix)
    display_sym = run_symbol.split(":")[-1].replace("-EQ", "").replace("-INDEX", "")

    # Patch config.json with selected market & resolved symbol
    patch_config(market, run_symbol)

    # Run the actual agent
    from main import run
    result = run(symbol=run_symbol, mode="LIVE_DATA", allow_network=True)

    # Print friendly output — use clean display name and correct currency
    friendly_output(result, display_sym, market)

    # Offer to run again
    again = ask("  Analyse another stock? (Y / N):", options=["Y", "N"])
    if again == "Y":
        main()
    else:
        print(f"\n{CYAN}  Thank you for using Agent 1. Goodbye!{RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}  Cancelled. Goodbye!{RESET}\n")
