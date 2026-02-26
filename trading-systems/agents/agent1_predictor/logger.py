import logging
import os
from datetime import datetime

# --- Logging Infrastructure ---
# We store logs in a local 'logs' directory to keep the root clean.
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# We use a daily rotating file format (agent1_YYYYMMDD.log) 
# for easier auditing and debugging across different trading days.
today_str = datetime.now().strftime("%Y%m%d")
log_filename = os.path.join(LOGS_DIR, f"agent1_{today_str}.log")

# Create the primary logger instance
logger = logging.getLogger("Agent1")
logger.setLevel(logging.INFO)

# --- Handler 1: Console Output ---
# This allows developers to see real-time progress in the terminal.
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# --- Handler 2: Persistent File Log ---
# This ensures a permanent record of decisions, errors, and Guardian veteos is saved.
fh = logging.FileHandler(log_filename)
fh.setLevel(logging.INFO)

# --- Standardized Formatting ---
# Format: Time - Module - Level - Message
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)

# Prevent duplicate handlers if the logger is re-initialized multiple times
if not logger.hasHandlers():
    logger.addHandler(ch)
    logger.addHandler(fh)

def get_logger():
    """Returns the pre-configured global logger."""
    return logger
