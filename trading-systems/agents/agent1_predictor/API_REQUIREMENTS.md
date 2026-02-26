# Agent 1: API Requirements Checklist

To unlock the full potential of Agent 1 (Intelligence & Execution), you will need the following API keys.

## 🔷 Intelligence (LLM Reasoning)
*Used for qualitative decision explanation.*

| Provider | Purpose | Where to Get |
| :--- | :--- | :--- |
| **OpenAI (Primary)** | GPT-4o-mini reasoning | [OpenAI Platform](https://platform.openai.com/) |
| **Anthropic** | Claude 3 Haiku fallback | [Anthropic Console](https://console.anthropic.com/) |
| **Google** | Gemini Pro fallback | [Google AI Studio](https://aistudio.google.com/) |

---

## 📊 Market Data (OHLCV & Prices)
*Used for technical indicator calculation.*

| Provider | Purpose | Where to Get |
| :--- | :--- | :--- |
| **yFinance** | Default (Free, No Key) | Built-in (Default) |
| **Polygon.io** | Institutional-grade data | [Polygon Dashboard](https://polygon.io/) |
| **Alpha Vantage** | Backup data feed | [Alpha Vantage Website](https://www.alphavantage.co/) |

---

## 💰 Execution (Trading)
*Used for placing orders.*

| Provider | Purpose | Where to Get |
| :--- | :--- | :--- |
| **Alpaca** | Paper Trading (Free) | [Alpaca Markets](https://alpaca.markets/) |

---

## 🔐 How to Add Keys
1. Open the file named `.env` in the project root.
2. Paste your keys next to the corresponding variable:
   ```env
   OPENAI_API_KEY=sk-...
   ALPACA_API_KEY=...
   ALPACA_SECRET_KEY=...
   ```
3. Save the file. The `config.py` loader will detect them automatically.
