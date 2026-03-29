# 🤖 Agent 1 — AI Stock Analyser

An AI-powered stock analysis engine for **Indian (NSE/BSE)** and **US** markets.
It fetches live data, runs high-speed technical analysis across multiple indicators, and outputs a **BUY / SELL / HOLD** recommendation equipped with strict risk-guardian gating and LLM-driven reasoning.

---

## 🚀 What's New: Phase 3 & Phase 5 Architecture Upgrades

The entire core engine has been upgraded for production-grade speed and real-time responsiveness:

*   **Phase 3 (Latency Reduction):** Indicators are no longer calculated in a slow, blocking sequence. The `indicator_engine` has been refactored into pure mathematical functions dispatched asynchronously via `async_engine.py` into a robust `ThreadPoolExecutor`. Expect **5×–20×** performance gains on feature extraction.
*   **Phase 5 (Live WebSocket Data):** Slow HTTP polling is dead. We integrated a push-based streaming model via `websocket_client.py`. 
    *   **Fyers WebSocket integration** maps native tick data into live-forming OHLCV candles dynamically.
    *   **Simulator Fallback:** If you don't use Fyers, the engine seamlessly bootstraps an ultra-realistic random-walk micro-ticker using historical ATR volatility.
*   **Real-time FastAPI Endpoint:** We deployed a fast streaming gateway via `uvicorn api_layer.server:app`. Watch the AI analyze every nanosecond tick live by opening **`test_dashboard.html`** in your browser!

---

## 📁 File Overview

```
agent1_predictor/
│
├── run_agent.py          ← START HERE — guided interactive launcher
├── main.py               ← Core engine (called by run_agent.py)
├── async_engine.py       ← [NEW] High-performance asynchronous threading pipeline
│
├── fyers_mcp_auth.py     ← Daily login for Indian stocks (run every morning)
│
├── config.py             ← Loads API keys from .env
├── config.json           ← Settings (symbol, interval, provider, risk rules)
├── .env                  ← Your secret API keys (never share this file)
│
├── api_layer/            ← [NEW] FastAPI websocket server (server.py, analysis_routes.py)
├── data_layer/           ← Data ingestors + [NEW] websocket_client.py
├── indicator_engine/     ← Pure math functions (EMA, RSI, MACD, ATR, OBV) dispatched in parallel
├── fusion_engine/        ← Regime detection, strategy mapping, and confidence scoring
├── reasoning_engine/     ← AI explanation engine (Gemini 2.0 Flash → OpenRouter → Deterministic Fallback)
├── guardian.py           ← Risk safety checker (blocks bad trades based on ATR levels)
├── validator.py          ← Output quality checker (JSON schema + logic rules)
│
├── test_dashboard.html   ← [NEW] Real-time visual dashboard (open in Chrome!)
├── requirements.txt      ← All Python libraries needed
└── logs/                 ← All run logs saved here (auto-created)
```

---

## ⚡ Quick Start

### Step 1 — Install Python Subsystems
Make sure Python 3.10+ is installed, then set up your virtual environment and install dependencies:
```powershell
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
pip install fastapi uvicorn websockets fyers-apiv3  # Phase 5 requirements
```

### Step 2 — Set Up API Keys
Fill in your `.env` file:
```env
# AI Reasoning
GOOGLE_API_KEY=your_google_gemini_key       # Free at aistudio.google.com
OPENROUTER_API_KEY=your_openrouter_key      # Free at openrouter.ai

# Fyers — required for Indian stocks only
FYERS_APP_ID=PXE70PDXO1-100                 # From myapi.fyers.in
FYERS_SECRET_KEY=your_fyers_secret
FYERS_ACCESS_TOKEN=                         # Auto-filled by fyers_mcp_auth.py
```

---

## 📡 Live Streaming Mode (Phase 5)

If you want to observe the AI analyzing a stock in real-time as ticks hit the exchange:

1. **Boot the Server:**
   ```powershell
   uvicorn api_layer.server:app --port 8000
   ```
2. **Open the Dashboard:** Double click `test_dashboard.html` to instantly connect to the WebSocket and watch Live JSON predictions & LLM reasoning flow through your browser!

---

## 🖥️ CLI Mode (Standard Mode)

If you just want a quick breakdown in terminal English:

```powershell
python run_agent.py
```

The terminal will launch an interactive wizard asking you which market (US or India) and which stock you'd like an immediate report on.

*(Note for Indian Stocks):* You must run `python fyers_mcp_auth.py` once every morning to authenticate your Fyers session before running the agent.

---

## 📊 How the Core Engine Works

```
Fetch Fast Historical Data
            ↓  
[Thread Pool Async Exec] → EMA, MACD, RSI, OBV, VWAP, ATR
            ↓  
[Fusion Engine] → Detects Regime (Hurst Exponent)
            ↓  
Calculates Net Confidence Score (0%-100%)
            ↓  
[Guardian Gate] → Blocks trade if Stop-Loss is too tight or confidence < 55%
            ↓  
[LLM Router] → Asks Gemini 2.0 Flash to explain mathematically WHY we are executing
```

### AI Reasoning — Fallback Chain
If the stock exchange pushes data but the remote AI limits out, the pipeline never breaks. It falls back organically:
`Gemini 2.0 Flash` → `OpenRouter` → `OpenAI` → `Offline Deterministic Local Engine`

---

## ⚠️ Disclaimer
*Agent 1 is a quantitative research prototype currently in testing phases. It is not financial advice. Always paper trade and backtest rigorously before attaching real capital. Past analysis does not guarantee future results.*
