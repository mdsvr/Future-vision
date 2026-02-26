import json
import os
import time
from config import Config
from logger import get_logger

# Optional: Attempt to load the OpenAI library for intelligence-driven reasoning
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = get_logger()

class LLMRouter:
    """
    Intelligent Reasoning Router.
    This class manages the interaction with various LLM providers (OpenAI, Claude, etc.)
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

    def generate_reasoning(self, symbol, regime, signals, confidence, atr_percentile):
        """
        Main entry point for generating descriptive reasoning.
        Priority:
        1. Local fallback if network is disabled.
        2. Remote API (e.g. OpenAI) if allowed and configured.
        3. Local fallback if API fails.
        """
        # 🛡️ Safety: Block network if not explicitly allowed via CLI
        if not self.allow_network:
            logger.info("LLM Network disabled - Using deterministic (local) fallback reasoning.")
            return self._fallback_reasoning(symbol, regime, signals, confidence, atr_percentile)

        # Execute Intelligent Reasoning
        try:
            if self.provider == "openai" and OpenAI:
                 return self._openai_reasoning(symbol, regime, signals, confidence)
            
            # --- Future Providers (Claude/Gemini) can be added here ---
            
            # Default to fallback if provider is unknown
            return self._fallback_reasoning(symbol, regime, signals, confidence, atr_percentile)
        except Exception as e:
            logger.error(f"LLM Provider {self.provider} failed: {e}")
            if self.config.get("fallback_to_deterministic", True):
                return self._fallback_reasoning(symbol, regime, signals, confidence, atr_percentile)
            return "Reasoning temporarily unavailable (LLM Service Error)."

    def _openai_reasoning(self, symbol, regime, signals, confidence):
        """Calls OpenAI GPT-4o-mini to explain the trading signal."""
        start_request_time = time.time()
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        
        # We provide context but keep the prompt strict to ensure concise output
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
            temperature=0.3, # Low temperature for consistency
            max_tokens=150
        )
        latency = int((time.time() - start_request_time) * 1000)
        logger.info(f"OpenAI intelligence reasoning generated in {latency}ms")
        return response.choices[0].message.content.strip()

    def _fallback_reasoning(self, symbol, regime, signals, confidence, atr_percentile):
        """
        The deterministic 'Safety Net' for reasoning. 
        Ensures the agent always explains itself, even without an internet connection.
        """
        signal_summary = ", ".join([f"{k}: {v}" for k, v in signals.items()])
        
        # Volatility description based on ATR percentile
        vol_label = "extreme" if atr_percentile > 0.9 else "high" if atr_percentile > 0.7 else "low" if atr_percentile < 0.3 else "stable"
        
        reasoning = (
            f"System Analysis for {symbol} (Deterministic Mode):\n"
            f"1. Market State: Detected '{regime}' environment with {vol_label} volatility (ATR Rank: {atr_percentile:.2f}).\n"
            f"2. Signal Mix: [{signal_summary}].\n"
            f"3. Confidence: {confidence:.2f} score.\n"
        )
        
        # Append logic conclusion
        direction_sum = sum(signals.values())
        if confidence < 0.55:
             reasoning += "-> Conclusion: Market noise/uncertainty is high. Action prioritized as HOLD (Safety first)."
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
