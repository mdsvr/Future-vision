import os
from dotenv import load_dotenv

# --- Initialize Environment Variables ---
# We look for the .env file in the same directory as this config.py file.
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

class Config:
    """
    Centralized configuration class to manage API keys and environment variables.
    Exposes static attributes for clean access throughout the application.
    """
    
    # --- LLM API Keys ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # --- Exchange & Execution Keys ---
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
    # Default to paper trading URL if not specified
    ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    
    # --- Market Data Feed Keys ---
    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
    ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
    
    # --- News Sentiment Keys ---
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")

    @classmethod
    def validate_provider(cls, provider: str):
        """
        Security helper to fail-fast if a chosen module is missing its required credentials.
        :param provider: The service name (e.g., 'openai', 'alpaca', 'polygon')
        :raises ValueError: If the required keys are not found in the environment.
        """
        if provider == "openai" and not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY missing in .env")
        if provider == "claude" and not cls.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY missing in .env")
        if provider == "gemini" and not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY missing in .env")
        if provider == "polygon" and not cls.POLYGON_API_KEY:
            raise ValueError("POLYGON_API_KEY missing in .env")
        if provider == "alphavantage" and not cls.ALPHAVANTAGE_API_KEY:
            raise ValueError("ALPHAVANTAGE_API_KEY missing in .env")
        if provider == "alpaca" and (not cls.ALPACA_API_KEY or not cls.ALPACA_SECRET_KEY):
            raise ValueError("Alpaca keys missing in .env. Both KEY and SECRET are required.")
