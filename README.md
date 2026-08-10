# Future Vision — Agentic AI Trading

An autonomous multi-agent trading framework. **Agent 1 (Alpha)** is the first production component: an AI stock analyser for **Indian (NSE/BSE)** and **US** markets that fetches live data, runs technical analysis, and outputs **BUY / SELL / HOLD** recommendations with risk-guardian gating and LLM-driven reasoning.

---

## Repository layout

```
Future vision/
├── README.md                          ← you are here
└── trading-systems/
    └── agents/
        └── agent1_predictor/          ← Agent 1 — main application
            ├── run_agent.py           ← START HERE (CLI)
            ├── main.py                ← Core prediction pipeline
            ├── api_layer/             ← FastAPI + WebSocket server
            ├── data_layer/            ← Market data (yfinance, Fyers)
            ├── indicator_engine/      ← EMA, RSI, MACD, ATR, OBV, VWAP
            ├── fusion_engine/         ← Regime detection, signals, confidence
            ├── reasoning_engine/      ← LLM explanation (Gemini → fallback)
            ├── guardian.py            ← Risk safety gate
            ├── test_dashboard.html    ← Live analysis dashboard
            └── README.md              ← Detailed Agent 1 documentation
```

---

## Quick start

All commands below assume you are in the Agent 1 directory:

```powershell
cd trading-systems/agents/agent1_predictor
```

### 1. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install fastapi uvicorn websockets redis aiohttp loguru pydantic pytest
```

### 2. Configure environment

```powershell
copy .env.example .env
```

Edit `.env` with your API keys (see [Agent 1 README](trading-systems/agents/agent1_predictor/README.md) for details).

### 3. Run

**CLI (interactive analysis):**

```powershell
python run_agent.py
```

**API + live dashboard:**

```powershell
uvicorn api_layer.server:app --port 8000
```

Then open `test_dashboard.html` in your browser.

**Indian stocks:** run `python fyers_mcp_auth.py` once each morning to refresh your Fyers token.

---

## How Agent 1 works

```
Market data (yfinance / Fyers)
        ↓
Async indicator engine (EMA, MACD, RSI, OBV, VWAP, ATR)
        ↓
Fusion engine (regime + 5 strategy signals + confidence)
        ↓
Guardian (confidence gate, stop-loss gap, R:R ≥ 2:1)
        ↓
LLM reasoning (Gemini → OpenRouter → deterministic fallback)
        ↓
Validated JSON prediction (BUY / SELL / HOLD)
```

---

## Tests

```powershell
cd trading-systems/agents/agent1_predictor
python -m pytest test_confidence.py test_reasoning.py -v
```

---

## Documentation

For full setup, architecture notes, and API details, see:

**[trading-systems/agents/agent1_predictor/README.md](trading-systems/agents/agent1_predictor/README.md)**

---

## Disclaimer

Agent 1 is a quantitative research prototype in testing. It is not financial advice. Paper trade and backtest before using real capital.
