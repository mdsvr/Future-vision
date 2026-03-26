import json
import os
import time
from config import Config
from logger import get_logger

# Structured deterministic explanation engine (offline, no API needed)
try:
    from reasoning_engine.explanation_builder import build_explanation as _build_explanation
    _explanation_available = True
except ImportError:
    _explanation_available = False

# Optional: Attempt to load the OpenAI library for intelligence-driven reasoning
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Optional: Attempt to load Google Generative AI for Gemini reasoning
# Using the NEW google-genai SDK (replaces deprecated google.generativeai)
try:
    from google import genai as genai_client
    _genai_available = True
except ImportError:
    genai_client = None
    _genai_available = False

logger = get_logger()

class LLMRouter:
    """
    Intelligent Reasoning Router.
    This class manages the interaction with various LLM providers (OpenAI, OpenRouter, Gemini, etc.)
    and enforces a strict 'Deterministic Fallback' if network or APIs fail.
    """
    def __init__(self, provider="openai", allow_network=False):
        self.provider = provider
        self.allow_network = allow_network
        self.config = self._load_config()

    def _load_config(self):
        """Loads specific intelligence settings from config.json."""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r") as f:
            return json.load(f)["intelligence"]

    def generate_reasoning(self, symbol, regime, signals, confidence, atr_percentile, raw_indicators=None):
        """
        Main entry point for generating descriptive reasoning.
        Priority:
        1. Local fallback if network is disabled.
        2. Remote API (e.g. Gemini) if allowed and configured.
        3. Local fallback if API fails.

        Args:
            raw_indicators (dict, optional): Raw indicator values for use in
                offline explanation_builder. Keys: rsi, macd, macd_signal, stoch_rsi.
        """
        # Safety: Block network if not explicitly allowed via CLI
        if not self.allow_network:
            logger.info("LLM Network disabled - Using deterministic (local) fallback reasoning.")
            return self._fallback_reasoning(symbol, regime, signals, confidence, atr_percentile, raw_indicators)


        # Cascade: try each provider in order, fallback to next on failure
        providers_to_try = []

        # Always try Gemini first (free, fast)
        if _genai_available and Config.GOOGLE_API_KEY:
            providers_to_try.append("gemini")
        # Then OpenRouter (free models available)
        if OpenAI and Config.OPENROUTER_API_KEY:
            providers_to_try.append("openrouter")
        # Then OpenAI (paid, most capable)
        if OpenAI and Config.OPENAI_API_KEY and Config.OPENAI_API_KEY != "your_openai_key":
            providers_to_try.append("openai")

        for provider in providers_to_try:
            try:
                if provider == "gemini":
                    return self._gemini_reasoning(symbol, regime, signals, confidence, atr_percentile)
                elif provider == "openrouter":
                    return self._openrouter_reasoning(symbol, regime, signals, confidence)
                elif provider == "openai":
                    return self._openai_reasoning(symbol, regime, signals, confidence)
            except Exception as e:
                logger.error(f"LLM Provider {provider} failed: {e}")
                continue  # Try next provider

        # All providers failed — use deterministic
        logger.warning("All LLM providers failed or unavailable. Using deterministic reasoning.")
        return self._fallback_reasoning(symbol, regime, signals, confidence, atr_percentile)

    def _openai_reasoning(self, symbol, regime, signals, confidence):
        """Calls OpenAI GPT-4o-mini to explain the trading signal."""
        start_request_time = time.time()
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        
        prompt = (
            f"Asset: {symbol}\n"
            f"Market Regime: {regime}\n"
            f"Signals: {signals}\n"
            f"System Confidence: {confidence}\n\n"
            "Task: Explain this trading decision professionally. "
            "Focus on how the signals align with the market regime. "
            "Keep it under 3 sentences. Return text ONLY."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150
        )
        latency = int((time.time() - start_request_time) * 1000)
        logger.info(f"OpenAI intelligence reasoning generated in {latency}ms")
        return response.choices[0].message.content.strip()

    def _openrouter_reasoning(self, symbol, regime, signals, confidence):
        """Calls OpenRouter API using the standard OpenAI client schema."""
        start_request_time = time.time()
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=Config.OPENROUTER_API_KEY,
        )
        
        prompt = (
            f"Asset: {symbol}\n"
            f"Market Regime: {regime}\n"
            f"Signals: {signals}\n"
            f"System Confidence: {confidence}\n\n"
            "Task: Explain this trading decision professionally. "
            "Focus on how the signals align with the market regime. "
            "Keep it under 3 sentences. Return text ONLY."
        )

        # Free models on OpenRouter (in preference order).
        # If a model is deleted or unavailable (404), the next one is tried.
        FREE_MODELS = [
            "google/gemma-3-27b-it:free",         # Google Gemma 3 27B (best free)
            "deepseek/deepseek-r1:free",           # DeepSeek R1 reasoning model
            "meta-llama/llama-3.1-8b-instruct:free", # Llama 3.1 8B (updated name)
            "mistralai/mistral-7b-instruct:free",  # Mistral 7B (reliable fallback)
        ]

        last_error = None
        for model in FREE_MODELS:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=150
                )
                latency = int((time.time() - start_request_time) * 1000)
                logger.info(f"OpenRouter ({model}) reasoning generated in {latency}ms")
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"OpenRouter model {model} failed: {e}")
                last_error = e
                continue

        # All models failed — raise the last error to trigger the outer cascade
        raise Exception(f"All OpenRouter free models failed. Last error: {last_error}")

    def _gemini_reasoning(self, symbol, regime, signals, confidence, atr_percentile):
        """
        Calls Google Gemini 2.0 Flash (free tier) using the new google.genai SDK.
        Requires GOOGLE_API_KEY in .env.
        """
        start_request_time = time.time()

        # Initialise client with the new SDK
        client = genai_client.Client(api_key=Config.GOOGLE_API_KEY)

        prompt = (
            f"Asset: {symbol}\n"
            f"Market Regime: {regime}\n"
            f"Signals: {signals}\n"
            f"System Confidence: {confidence}\n"
            f"ATR Percentile (Volatility): {atr_percentile:.2f}\n\n"
            "Task: Explain this trading decision professionally. "
            "Focus on how the signals align with the market regime. "
            "Keep it under 3 sentences. Return text ONLY."
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        latency = int((time.time() - start_request_time) * 1000)
        logger.info(f"Gemini intelligence reasoning generated in {latency}ms")
        return response.text.strip()

    def _fallback_reasoning(self, symbol, regime, signals, confidence, atr_percentile, raw_indicators=None):
        """
        Deterministic 'Safety Net' for reasoning.
        Uses the structured explanation_builder when available for rich offline narratives.
        Falls back to minimal summary when explanation_builder is not importable.

        Args:
            raw_indicators (dict, optional): Raw indicator values for richer explanations.
                Expected keys: rsi, macd, macd_signal, stoch_rsi
        """
        # ── Rich structured explanation (preferred) ───────────────────────────
        if _explanation_available and raw_indicators:
            try:
                return _build_explanation(
                    signals        = signals,
                    regime         = regime,
                    rsi_val        = raw_indicators.get("rsi", 50.0),
                    macd_val       = raw_indicators.get("macd", 0.0),
                    macd_sig_val   = raw_indicators.get("macd_signal", 0.0),
                    stoch_val      = raw_indicators.get("stoch_rsi", 0.5),
                    atr_percentile = atr_percentile,
                    confidence     = confidence,
                )
            except Exception as e:
                logger.warning(f"explanation_builder failed: {e}. Falling back to minimal summary.")

        # ── Minimal summaryfall back (no indicator values available) ──────────
        signal_summary = ", ".join([f"{k}: {v}" for k, v in signals.items()])
        vol_label = (
            "extreme" if atr_percentile > 0.9
            else "high" if atr_percentile > 0.7
            else "low" if atr_percentile < 0.3
            else "stable"
        )

        reasoning = (
            f"System Analysis for {symbol} (Deterministic Mode):\n"
            f"1. Market State: Detected '{regime}' environment with {vol_label} volatility (ATR Rank: {atr_percentile:.2f}).\n"
            f"2. Signal Mix: [{signal_summary}].\n"
            f"3. Confidence: {confidence:.3f} ({confidence * 100:.1f}%).\n"
        )

        direction_sum = sum(signals.values())
        if confidence < 0.55:
            reasoning += "-> Conclusion: Market noise/uncertainty is high. Action prioritized as HOLD."
        elif direction_sum > 0:
            reasoning += "-> Conclusion: Indicators show bullish momentum/trend alignment. Action: BUY."
        elif direction_sum < 0:
            reasoning += "-> Conclusion: Indicators show bearish pressure/reversion potential. Action: SELL."
        else:
            reasoning += "-> Conclusion: Signals are net-neutral. Action: HOLD."

        return reasoning

def generate_reasoning(symbol, regime, signals, confidence, atr_percentile):
    """Utility function for simple imports if class-instantiation is not needed."""
    router = LLMRouter(allow_network=False) 
    return router.generate_reasoning(symbol, regime, signals, confidence, atr_percentile)
