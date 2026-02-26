# Agent 1: Intelligent Trading Predictor (v3.0)

Agent 1 is a "Right-Sized" trading prototype that combines deterministic quantitative analysis with LLM-powered qualitative reasoning. It is designed with a **Safety-First** architecture, ensuring that every trade is validated by a rigorous **Guardian** layer before execution.

## 🏗️ Core Architecture

- **Quant Engine**: Calculates technical indicators (EMA, RSI, MACD, ATR, OBV) and detects market regimes (Trend, Mean Reversion, Random).
- **LLM Router**: Multi-provider intelligence layer (OpenAI, Claude, Gemini) for professional decision reasoning.
- **Guardian Layer**: A hard-coded safety net that blocks trades based on low confidence, extreme volatility, or poor risk/reward ratios.
- **Execution Agent**: Integrated Alpaca paper trading for real-time testing.
- **Validator**: Ensures all internal data structures meet strict schema requirements.

---

## 🚦 Runtime Modes

Agent 1 uses a mode-based execution system to prevent accidental live actions:

| Mode | Command | Network | Execution | Use Case |
| :--- | :--- | :---: | :---: | :--- |
| **SAFE** | `py main.py --mode SAFE` | ❌ | ❌ | Local logic testing / Debugging. |
| **LIVE_DATA** | `py main.py --mode LIVE_DATA --allow-network` | ✅ | ❌ | Real signals & LLM analysis. |
| **PAPER** | `py main.py --mode PAPER --allow-network` | ✅ | ✅ | Active Paper Trading on Alpaca. |

---

## 🛠️ Setup & Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Secrets**:
   - Copy `.env.example` to `.env`.
   - Populate with your API keys (see `API_REQUIREMENTS.md`).

3. **Tune Parameters**:
   - Edit `config.json` to adjust entry thresholds, risk percentiles, and technical periods.

---

## 🔐 Safety Guarantees

1. **Hierarchy of Authority**: The Quant Engine & Guardian always override the LLM. If the numbers don't add up, the LLM's opinion is disregarded.
2. **Network Lock**: No external calls are made unless `--allow-network` is explicitly typed.
3. **Deterministic Fallback**: If an LLM API is down or keys are missing, the system automatically uses locally-coded reasoning rules to ensure zero downtime.
4. **Validation**: Every prediction is JSON-schema validated before being logged or sent to execution.
