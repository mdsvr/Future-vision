"""
demo.py  —  Live Indicator Output Demo
========================================
Fetches real market data and runs every indicator function from indicators.py,
printing a clean, formatted output showing what each formula produces.

HOW TO RUN:
    py demo.py              ← Uses default (RELIANCE via Fyers if .env set, else AAPL)
    py demo.py AAPL         ← US stock
    py demo.py NSE:TCS-EQ   ← Indian stock (Fyers token required)

OUTPUT:
    Shows the last candle's value for every indicator, the signals generated,
    and the final confidence score — in plain English.
"""

import sys
import os
import pandas as pd

# ── Load our indicator functions ──────────────────────────────────────────────
from indicators import (
    ema, rsi, macd, bollinger_bands, stochastic_rsi,
    atr, obv, obv_slope, vwap,
    hurst_exponent, classify_regime,
    ema_trend_signal, rsi_signal, stoch_rsi_signal, bollinger_signal,
    confidence_score
)

# ── Formatting helpers ─────────────────────────────────────────────────────────
CYAN   = "\033[96m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

def hr(char="─", width=62):
    print(DIM + char * width + RESET)

def section(title):
    print()
    hr()
    print(BOLD + f"  {title}" + RESET)
    hr()

def row(label, value, unit="", color=None, width=30):
    col = color or ""
    print(f"  {label:<{width}}  {col}{value}{RESET}{unit}")

def signal_str(s):
    if s > 0:   return GREEN + f"+{s}" + RESET
    if s < 0:   return RED   + f"{s}" + RESET
    return YELLOW + "0 (neutral)" + RESET


# ── Fetch data ─────────────────────────────────────────────────────────────────
def fetch_data(symbol: str) -> pd.DataFrame:
    """Fetches OHLCV data using the project's data_ingestion module."""
    from data_ingestion import fetch_ohlcv
    import json, os

    # Temporarily override the symbol in config for the fetch
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(cfg_path) as f:
        import json
        cfg = json.load(f)

    # Determine provider
    provider_name = cfg["data"].get("market_data_provider", "yfinance")
    interval = cfg["data"]["interval"]
    period   = cfg["data"]["period"]

    if symbol.startswith("NSE:") or symbol.startswith("BSE:"):
        # Override to fyers if symbol looks like Indian format
        from data_ingestion import FyersProvider
        df = FyersProvider().fetch(symbol, interval, period)
    else:
        from data_ingestion import YFinanceProvider
        df = YFinanceProvider().fetch(symbol, "15m", "30d")

    return df


def main():
    # ── Symbol selection ───────────────────────────────────────────────────────
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    currency = "₹" if (symbol.startswith("NSE:") or symbol.startswith("BSE:")) else "$"
    display  = symbol.replace("NSE:", "").replace("-EQ", "").replace("-BE", "")

    print()
    print(BOLD + CYAN + "=" * 62 + RESET)
    print(BOLD + f"   INDICATOR DEMO  —  {display}" + RESET)
    print(BOLD + CYAN + "=" * 62 + RESET)
    print(f"  Fetching data for: {CYAN}{symbol}{RESET}")

    # ── Fetch & validate ───────────────────────────────────────────────────────
    df = fetch_data(symbol)
    if df is None or df.empty or len(df) < 50:
        print(RED + "\n  Error: Not enough data. Check symbol or connection.\n" + RESET)
        return

    close  = df['close']
    high   = df['high']
    low    = df['low']
    volume = df['volume']
    last   = close.iloc[-1]
    prev   = close.iloc[-2]
    pct_chg= (last - prev) / prev * 100

    print(f"  Loaded: {CYAN}{len(df):,} candles{RESET}\n")

    # ══════════════════════════════════════════════════════════════
    section("PRICE SUMMARY (Last Candle)")
    row("Close Price",   f"{currency}{last:,.2f}",       color=GREEN if pct_chg >= 0 else RED)
    row("Open",          f"{currency}{df['open'].iloc[-1]:,.2f}")
    row("High",          f"{currency}{high.iloc[-1]:,.2f}")
    row("Low",           f"{currency}{low.iloc[-1]:,.2f}")
    row("Volume",        f"{volume.iloc[-1]:,.0f}")
    row("Change",        f"{pct_chg:+.2f}%",             color=GREEN if pct_chg >= 0 else RED)

    # ══════════════════════════════════════════════════════════════
    section("TREND INDICATORS")

    # EMA
    ema50_s  = ema(close, 50);  ema50  = ema50_s.iloc[-1]
    ema200_s = ema(close, 200); ema200 = ema200_s.iloc[-1]

    above50  = last > ema50
    above200 = last > ema200

    row("EMA 50",  f"{currency}{ema50:,.2f}",  color=GREEN if above50  else RED)
    row("EMA 200", f"{currency}{ema200:,.2f}", color=GREEN if above200 else RED)
    row("Price vs EMA50",
        ("ABOVE ↑" if above50  else "BELOW ↓"),
        color=GREEN if above50  else RED)
    row("Price vs EMA200",
        ("ABOVE — Bullish long-term" if above200 else "BELOW — Bearish long-term"),
        color=GREEN if above200 else RED)

    # VWAP
    vwap_s = vwap(high, low, close, volume)
    vwap_v = vwap_s.iloc[-1]
    vs_vwap = last > vwap_v
    row("VWAP",    f"{currency}{vwap_v:,.2f}",  color=GREEN if vs_vwap else RED)
    row("Price vs VWAP",
        ("ABOVE — Buyers in control" if vs_vwap else "BELOW — Sellers in control"),
        color=GREEN if vs_vwap else RED)

    # ══════════════════════════════════════════════════════════════
    section("MOMENTUM INDICATORS")

    # RSI
    rsi_s = rsi(close, 14)
    rsi_v = rsi_s.iloc[-1]
    rsi_color = RED if rsi_v > 70 else GREEN if rsi_v < 30 else YELLOW
    rsi_label = " (OVERBOUGHT ⚠)" if rsi_v > 70 else " (OVERSOLD ✓)" if rsi_v < 30 else " (Neutral)"
    row("RSI (14)", f"{rsi_v:.1f}{rsi_label}", color=rsi_color)

    # Stochastic RSI
    srsi_s = stochastic_rsi(close, 14)
    srsi_v = srsi_s.iloc[-1]
    srsi_color = RED if srsi_v > 0.8 else GREEN if srsi_v < 0.2 else YELLOW
    srsi_label = " (OVERBOUGHT)" if srsi_v > 0.8 else " (OVERSOLD)" if srsi_v < 0.2 else " (Neutral)"
    row("Stochastic RSI", f"{srsi_v:.3f}{srsi_label}", color=srsi_color)

    # MACD
    macd_d   = macd(close)
    macd_v   = macd_d["macd"].iloc[-1]
    sig_v    = macd_d["signal"].iloc[-1]
    hist_v   = macd_d["histogram"].iloc[-1]
    macd_bull= macd_v > sig_v
    row("MACD Line",    f"{macd_v:.4f}", color=GREEN if macd_bull else RED)
    row("MACD Signal",  f"{sig_v:.4f}")
    row("MACD Histogram", f"{hist_v:+.4f} ({'Bullish momentum' if hist_v > 0 else 'Bearish momentum'})",
        color=GREEN if hist_v > 0 else RED)

    # ══════════════════════════════════════════════════════════════
    section("VOLATILITY INDICATORS")

    # ATR
    atr_s = atr(high, low, close, 14)
    atr_v = atr_s.iloc[-1]
    atr_pct = float(atr_s.rank(pct=True).iloc[-1])
    row("ATR (14)",          f"{currency}{atr_v:.2f}   ← average candle range")
    row("ATR Percentile",    f"{atr_pct*100:.0f}th percentile   "
        f"({'HIGH volatility' if atr_pct > 0.8 else 'LOW volatility' if atr_pct < 0.2 else 'Normal volatility'})",
        color=RED if atr_pct > 0.8 else GREEN if atr_pct < 0.2 else YELLOW)
    row("Suggested Stop Loss",
        f"{currency}{last - 2*atr_v:.2f}  (entry ± 2×ATR)",
        color=DIM)
    row("Suggested Target",
        f"{currency}{last + 4*atr_v:.2f}  (entry ± 4×ATR for 2:1 RR)",
        color=DIM)

    # Bollinger Bands
    bb = bollinger_bands(close, 20, 2.0)
    bb_u = bb["upper"].iloc[-1]
    bb_l = bb["lower"].iloc[-1]
    bb_m = bb["mid"].iloc[-1]
    bb_w = bb["width"].iloc[-1]
    bb_pos = "ABOVE UPPER BAND ↑ (Overbought)" if last > bb_u \
             else "BELOW LOWER BAND ↓ (Oversold)" \
             if last < bb_l else "Inside bands (Normal)"
    bb_color = RED if last > bb_u else GREEN if last < bb_l else YELLOW
    row("BB Upper",     f"{currency}{bb_u:,.2f}")
    row("BB Mid (SMA)", f"{currency}{bb_m:,.2f}")
    row("BB Lower",     f"{currency}{bb_l:,.2f}")
    row("BB Width",     f"{bb_w:.4f}   ({'Squeeze — big move coming' if bb_w < 0.03 else 'Normal range'})")
    row("Price Position", bb_pos, color=bb_color)

    # ══════════════════════════════════════════════════════════════
    section("VOLUME INDICATORS")

    obv_s     = obv(close, volume)
    obv_v     = obv_s.iloc[-1]
    obv_sl    = obv_slope(obv_s, 5).iloc[-1]
    vol_avg   = volume.rolling(20).mean().iloc[-1]
    vol_spike = volume.iloc[-1] > 1.5 * vol_avg

    row("OBV (cumulative)", f"{obv_v:,.0f}")
    row("OBV Slope (5c)",   f"{obv_sl:+,.0f}  ({'Volume flowing IN' if obv_sl > 0 else 'Volume flowing OUT'})",
        color=GREEN if obv_sl > 0 else RED)
    row("Volume (last)",    f"{volume.iloc[-1]:,.0f}")
    row("Volume Avg (20)",  f"{vol_avg:,.0f}")
    row("Volume Spike",     "YES ⚡" if vol_spike else "No",
        color=YELLOW if vol_spike else RESET)

    # ══════════════════════════════════════════════════════════════
    section("MARKET REGIME (Hurst Exponent)")

    h       = hurst_exponent(close.tail(200), max_lag=20)
    regime  = classify_regime(h)
    reg_col = GREEN if regime == "trending" else CYAN if regime == "mean_reverting" else YELLOW
    reg_desc= {
        "trending":       "Trend following works best. Buy breakouts, ride the move.",
        "mean_reverting": "Fade the move. Price will snap back to average.",
        "random":         "No clear pattern. Wait and watch.",
    }
    row("Hurst Exponent (H)", f"{h:.4f}")
    row("Market Regime",      regime.upper().replace("_", " "), color=reg_col)
    row("Strategy Advice",    reg_desc[regime], color=reg_col)

    # ══════════════════════════════════════════════════════════════
    section("TRADING SIGNALS  (5 Signals)")

    sig_trend = ema_trend_signal(last, ema50, ema200)
    sig_rsi   = rsi_signal(rsi_v)
    macd_cross= 1 if macd_v > sig_v else -1 if macd_v < sig_v else 0
    sig_mom   = round(0.6 * macd_cross + 0.4 * sig_rsi, 2)
    sig_bb    = bollinger_signal(last, bb_u, bb_l)
    sig_vol   = 1 if obv_sl > 0 else -1 if obv_sl < 0 else 0
    sig_srsi  = stoch_rsi_signal(srsi_v)

    signals = {
        "trend":         sig_trend,
        "momentum":      sig_mom,
        "mean_reversion":sig_bb,
        "volume":        sig_vol,
        "stoch_rsi":     sig_srsi,
    }

    row("1. Trend (EMA)",          f"  {signal_str(sig_trend)}")
    row("2. Momentum (MACD+RSI)",  f"  {signal_str(sig_mom)}")
    row("3. Mean Reversion (BB)",  f"  {signal_str(sig_bb)}")
    row("4. Volume (OBV slope)",   f"  {signal_str(sig_vol)}")
    row("5. Stochastic RSI",       f"  {signal_str(sig_srsi)}")

    bulls = sum(1 for v in signals.values() if v > 0)
    bears = sum(1 for v in signals.values() if v < 0)
    print()
    row("  Bullish signals", f"{bulls}/5", color=GREEN)
    row("  Bearish signals", f"{bears}/5", color=RED)

    # ══════════════════════════════════════════════════════════════
    section("CONFIDENCE SCORE")

    conf      = confidence_score(signals, regime, atr_pct)
    conf_pct  = int(conf * 100)
    direction = sum(signals.values())
    action    = "BUY" if direction > 0 else "SELL" if direction < 0 else "HOLD"
    if conf < 0.55:
        action = "HOLD"

    conf_color = GREEN if conf_pct >= 65 else YELLOW if conf_pct >= 45 else RED
    act_color  = GREEN if action == "BUY" else RED if action == "SELL" else YELLOW

    row("Regime-Weighted Score", f"{conf_pct}%", color=conf_color)
    row("Threshold to act",      "55% (below = forced HOLD)")
    row("Final Recommendation",  action, color=act_color)

    if action == "BUY":
        print(f"\n  {GREEN}→ Entry: {currency}{last:.2f}  |  Stop: {currency}{last - 2*atr_v:.2f}  |  Target: {currency}{last + 4*atr_v:.2f}{RESET}")
    elif action == "SELL":
        print(f"\n  {RED}→ Entry: {currency}{last:.2f}  |  Stop: {currency}{last + 2*atr_v:.2f}  |  Target: {currency}{last - 4*atr_v:.2f}{RESET}")
    else:
        print(f"\n  {YELLOW}→ Wait for clearer signal. Confidence {conf_pct}% is below the 55% threshold.{RESET}")

    print()
    print(BOLD + CYAN + "=" * 62 + RESET)
    print()


if __name__ == "__main__":
    main()
