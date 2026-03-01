# 🤖 Agent 1 — AI Stock Analyser

An AI-powered stock analysis engine for **Indian (NSE)** and **US** markets.
It fetches live data, runs technical analysis, and outputs a **BUY / SELL / HOLD** recommendation with entry price, stop-loss, and AI reasoning.

---

## 📁 File Overview

```
agent1_predictor/
│
├── run_agent.py          ← START HERE — guided interactive launcher
├── main.py               ← Core engine (called by run_agent.py)
│
├── fyers_mcp_auth.py     ← Daily login for Indian stocks (run every morning)
│
├── config.py             ← Loads API keys from .env
├── config.json           ← Settings (symbol, interval, provider, risk rules)
├── .env                  ← Your secret API keys (never share this file)
├── .env.example          ← Template showing which keys are needed
│
├── data_ingestion.py     ← Downloads price data (Fyers for India, yfinance for US)
├── feature_engine.py     ← Calculates technical indicators (EMA, RSI, MACD, ATR, OBV)
├── regime.py             ← Detects market type (trending / mean-reverting / random)
├── strategy_engine.py    ← Converts indicators → signals (+1 / 0 / -1)
├── confidence.py         ← Scores AI conviction (0% to 100%)
├── llm_reasoner.py       ← AI explanation engine (Gemini → OpenRouter → OpenAI)
├── guardian.py           ← Risk safety checker (blocks bad trades)
├── validator.py          ← Output quality checker (schema + logic rules)
├── execution_agent.py    ← Paper trade executor (standby — future use)
│
├── logger.py             ← Logging to terminal + logs/ folder
├── requirements.txt      ← All Python libraries needed
├── schema/               ← JSON schema for output validation
└── logs/                 ← All run logs saved here (auto-created)
```

---

## ⚡ Quick Start

### Step 1 — Install Python 3.10+
Download from [python.org](https://www.python.org/downloads/) if not installed.
```powershell
python --version    # Should show 3.10 or higher
```

### Step 2 — Install Libraries
Open a terminal in the `agent1_predictor` folder:
```powershell
py -m pip install -r requirements.txt
```

### Step 3 — Set Up API Keys
Copy `.env.example` to `.env` and fill in your keys:
```env
# AI Reasoning — agent tries these in order: Gemini → OpenRouter → OpenAI
GOOGLE_API_KEY=your_google_gemini_key       # Free at aistudio.google.com
OPENROUTER_API_KEY=your_openrouter_key      # Free at openrouter.ai

# Fyers — required for Indian stocks only
FYERS_APP_ID=PXE70PDXO1-100               # From myapi.fyers.in
FYERS_SECRET_KEY=your_fyers_secret
FYERS_ACCESS_TOKEN=                        # Auto-filled by fyers_mcp_auth.py
```
> US stocks (AAPL, TSLA etc.) work immediately with just `GOOGLE_API_KEY` — no Fyers needed.

---

## 🇮🇳 Indian Stocks — Daily Login (Do This Every Morning)

Fyers tokens expire at midnight IST. Before analysing Indian stocks each day:

```powershell
py fyers_mcp_auth.py
```

**What happens:**
1. Browser opens the Fyers login page
2. You log in with your Fyers username + password
3. Google opens in the browser with a long URL in the address bar
4. Copy that full URL and paste it into the terminal
5. Token is saved to `.env` automatically ✅

> **One-time setup:** Make sure `https://www.google.com/` is set as the redirect URL in your Fyers API app at [myapi.fyers.in](https://myapi.fyers.in).

---

## 🚀 Running the Agent

```powershell
py run_agent.py
```

The agent will ask you 3 questions:

```
Step 1 — Choose market:   1 = US Stocks   |   2 = India Stocks
Step 2 — Choose stock:    e.g. RELIANCE, TCS, AAPL, TSLA
Step 3 — Confirm & Run
```

**Indian stock shortcuts recognized:**
| You type | Agent uses |
|---|---|
| `HDFC` | `HDFCBANK` (post-merger) |
| `SBI` | `SBIN` |
| `AIRTEL` | `BHARTIAIRTEL` |
| `KOTAK` | `KOTAKBANK` |
| `ICICI` | `ICICIBANK` |

If you type a US stock (like `APPLE`) in India mode, the agent will warn you and offer to switch market automatically.

---

## 📊 How the Analysis Works

```
Fetch Data → Add Indicators → Detect Regime → Generate Signals
    ↓               ↓               ↓               ↓
Fyers/yfinance  EMA, RSI,       Hurst          Trend +/-
                MACD, ATR,      Exponent       Momentum +/-
                OBV                             Mean Rev +/-
                                                    ↓
                                            Score Confidence (0–100%)
                                                    ↓
                                     Guardian Safety Check
                                      (confidence, stop-loss,
                                       allocation, risk-reward)
                                                    ↓
                                        BUY / SELL / HOLD
                                      + AI Explanation (Gemini)
```

### Confidence Score Explained
| Score | Meaning | Agent Action |
|---|---|---|
| Below 55% | Not enough evidence | Forces **HOLD** (safety first) |
| 55–75% | Moderate conviction | **BUY or SELL** if other checks pass |
| 75%+ | High conviction | **BUY or SELL** with higher allocation |

### Guardian Safety Rules (all 4 must pass for BUY/SELL)
1. Confidence ≥ 55%
2. Stop-loss must be ≥ 1 ATR away from entry (can't be too tight)
3. Position size ≤ maximum allocation cap
4. Reward must be ≥ 2× the risk (2:1 risk-reward minimum)

---

## 📋 Sample Output

```
========================================================
      ANALYSIS REPORT  —  RELIANCE
========================================================

  RECOMMENDATION:  HOLD  (Wait & Watch)

  HOW CONFIDENT IS THE AI?
    45% confident  (LOW)
    (Below 55% = not confident enough → HOLD is forced for safety)

  WHAT IS THE MARKET DOING?
    The stock is going DOWN. Sellers are in control right now.

  PRICE DETAILS
    Current Price  :  ₹1,394.80

  AI EXPLANATION
    Market is in a mean-reverting state with mixed signals.
    Trend and momentum both bearish but insufficient conviction
    to act. Best to wait for clearer direction.

  SAFETY CHECK  (Guardian)
    PASSED — The safety system approved this analysis.
========================================================

  SUMMARY IN ONE LINE:
  Don't buy or sell RELIANCE right now. Confidence too low (45%). Wait.
```

---

## 🤖 AI Reasoning — Fallback Chain

The agent tries AI providers in this order. If one fails, it automatically tries the next:

```
1. Google Gemini (free, fastest)
2. OpenRouter — Llama 3 (free fallback)
3. OpenAI — GPT-4o Mini (paid)
4. Deterministic Mode (no AI, uses pure math — always works)
```

> If all three APIs fail (e.g., rate limits), the agent still works using deterministic rules. It just won't have an AI-written explanation.

---

## ❓ Common Issues & Fixes

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | `py -m pip install -r requirements.txt` |
| `Invalid symbol provided` | Make sure you typed a valid NSE ticker (e.g. `HDFCBANK`, not `HDFC`) |
| `FYERS_ACCESS_TOKEN missing` | Run `py fyers_mcp_auth.py` to log in |
| `429 Rate limit (Gemini)` | Free tier hit — agent auto-switches to OpenRouter |
| `redirectUrl mismatch` | Set redirect URL to `https://www.google.com/` on myapi.fyers.in |
| `Confidence too low` | Normal! Markets are often uncertain. Run during trading hours (9:15–15:30 IST) |
| `Guardian BLOCKED` | Normal safety behavior — the trade didn't meet risk requirements |
| Logs not appearing | Check the `logs/` folder for detailed run logs |

---

## 📁 Logs

All runs are saved in the `logs/` folder with date-stamped filenames:
```
logs/agent1_20260301.log
```

---

## ⚠️ Disclaimer

*Agent 1 is a research prototype. It is not financial advice.
Always paper trade and backtest before using real money.
Past analysis does not guarantee future results.*
