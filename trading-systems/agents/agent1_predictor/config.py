"""
config.py  —  Central Configuration Loader
==========================================
This is the FIRST file that runs when the agent starts.
It reads API keys from the .env file and settings from config.json,
and makes them available to every other module as a single Config object.

Think of this as the 'Settings Panel' of the entire agent.
If something isn't working, check here first.

Files it reads:
    .env         — Secret API keys (never share this file)
    config.json  — Trading parameters (safe to edit)
"""

import os
import json
from dotenv import load_dotenv

# ── Load the .env file ────────────────────────────────────────────────────────
# .env holds all sensitive keys (API tokens, passwords).
# We look for it in the same folder as this script.
_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_ENV_PATH)


class Config:
    """
    A simple container that holds ALL configuration values for Agent 1.
    
    How to use:
        from config import Config
        print(Config.FYERS_APP_ID)   # access any value directly
    
    All values are loaded once at startup. If you change .env,
    you must restart the agent for changes to take effect.
    """

    # ── LLM (AI Brain) API Keys ───────────────────────────────────────────────
    # These keys power the AI reasoning engine.
    # The agent tries them in order: Gemini → OpenRouter → OpenAI
    OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")          # OpenAI GPT (paid)
    OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")      # OpenRouter (free tier available)
    OPENROUTER_API_KEY_2= os.getenv("OPENROUTER_API_KEY_2")    # Backup OpenRouter key
    GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY")          # Google Gemini (free tier)

    # ── Market Data API Keys ──────────────────────────────────────────────────
    ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")   # Alpha Vantage (US stock data)

    # ── Fyers API (Indian NSE/BSE Stocks) ────────────────────────────────────
    # These are required to fetch Indian market data.
    # - APP_ID and SECRET_KEY are permanent (from myapi.fyers.in)
    # - ACCESS_TOKEN must be refreshed daily by running: py fyers_mcp_auth.py
    FYERS_APP_ID       = os.getenv("FYERS_APP_ID")             # e.g. PXE70PDXO1-100
    FYERS_SECRET_KEY   = os.getenv("FYERS_SECRET_KEY")         # e.g. Z11BVN8ISY
    FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")       # Refreshed daily

    # ── Alpaca (US Paper Trading) ─────────────────────────────────────────────
    # Alpaca allows us to place SIMULATED paper trades (no real money).
    # Paper trading URL is used so no real orders are placed accidentally.
    ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
    ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    # ── Config.json Settings ──────────────────────────────────────────────────
    # Load the non-secret settings from config.json (safe to edit)
    _CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

    @classmethod
    def load_json(cls):
        """Loads and returns the full config.json as a Python dictionary."""
        with open(cls._CONFIG_PATH, "r") as f:
            return json.load(f)
