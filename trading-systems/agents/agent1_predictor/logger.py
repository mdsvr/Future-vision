"""
logger.py  —  Centralised Logging Setup
========================================
Sets up a single logger that ALL other modules share.
Every important action in the agent prints to both:
  - The terminal (so you can see it live)
  - A log file in the 'logs/' folder (so you can review it later)

Why use a logger instead of print()?
  - Logs include timestamps: you know WHEN things happened
  - Log levels (INFO, WARNING, ERROR) let you filter by importance
  - One place to control all output formatting

Usage in any other file:
    from logger import get_logger
    logger = get_logger()
    logger.info("Something worked")
    logger.error("Something broke")
"""

import logging
import os
from datetime import datetime

# ── Log file location ─────────────────────────────────────────────────────────
# Logs are stored in a 'logs/' subfolder next to this script.
# Each session creates a new file with today's date in the name.
_LOG_DIR  = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)   # Create the folder if it doesn't exist

_LOG_FILE = os.path.join(_LOG_DIR, f"agent1_{datetime.now().strftime('%Y%m%d')}.log")

# ── Logger name ───────────────────────────────────────────────────────────────
# All modules use the same named logger so their output is combined.
_LOGGER_NAME = "Agent1"


def get_logger() -> logging.Logger:
    """
    Returns the shared Agent 1 logger.
    
    Call this at the top of any module:
        logger = get_logger()
    
    Then use:
        logger.info("Fetched 250 candles")      # normal events
        logger.warning("Rate limit hit")         # recoverable issues
        logger.error("API call failed: ...")     # failures
    """
    logger = logging.getLogger(_LOGGER_NAME)

    # Only configure once — avoid adding duplicate handlers if called multiple times
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)   # Capture everything DEBUG and above

        # ── Format: timestamp + level + message ──────────────────────────────
        # Example output:  2026-03-01 09:15:00,123 - Agent1 - INFO - Fetched 250 candles
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # ── Handler 1: Print to terminal ──────────────────────────────────────
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)   # Show INFO and above in terminal
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # ── Handler 2: Write to log file ──────────────────────────────────────
        file_handler = logging.FileHandler(_LOG_FILE)
        file_handler.setLevel(logging.DEBUG)     # Save EVERYTHING to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
