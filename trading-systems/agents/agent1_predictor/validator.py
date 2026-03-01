"""
validator.py  —  Output Quality Checker
========================================
Before the agent returns its final prediction to the user,
this module checks that the result is complete and follows trading rules.

TWO-STAGE VALIDATION:
  Stage 1 — Structure Check (JSON Schema):
      Is every required field present? Is confidence a number? Is action one of BUY/SELL/HOLD?
      Uses a formal JSON schema definition (schema/agent1_prediction.schema.json).

  Stage 2 — Domain Rules (Trading Logic):
      Even if the data is technically valid, does it make SENSE as a trade?
      Check A: BUY/SELL signals must have a risk-reward ratio of at least 2:1
      Check B: HOLD signals must have 0% allocation (you don't allocate money to "do nothing")

WHY VALIDATE?
  Without validation, a bug in main.py or the guardian could produce:
  - A BUY recommendation with missing entry price
  - A HOLD signal that also says "invest 10%"
  - Confidence values above 1.0 or below 0
  The validator catches these before they reach the user.

Used by: main.py → called as the final step before returning the prediction dict.
"""

import json
import os
from jsonschema import validate, ValidationError

# ── Load the JSON schema from the schema/ folder ──────────────────────────────
# The schema defines the exact structure every prediction must follow.
# Think of it as a "contract" that the output must satisfy.
_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__),
    "schema",
    "agent1_prediction.schema.json"
)
with open(_SCHEMA_PATH, "r") as f:
    _SCHEMA = json.load(f)


def validate_prediction(prediction: dict) -> tuple:
    """
    Validates an Agent 1 prediction dictionary.

    Args:
        prediction (dict): The full prediction output from main.py

    Returns:
        tuple: (is_valid, message)
            is_valid (bool): True = passed all checks, False = failed
            message  (str):  "SYSTEM_PASS" or a specific error description

    Example:
        ok, msg = validate_prediction(result)
        if not ok:
            print(f"Validation error: {msg}")
    """

    # ── Stage 1: JSON Schema Validation ───────────────────────────────────────
    # Checks that all required fields exist with correct data types.
    # If even one field is wrong or missing, this stage fails immediately.
    try:
        validate(instance=prediction, schema=_SCHEMA)
    except ValidationError as e:
        # Return a clear error message showing WHICH field failed
        return False, f"JSON_SCHEMA_ERROR: {e.message}"

    # ── Stage 2: Trading Logic Rules ──────────────────────────────────────────

    # Rule A: Active trades (BUY or SELL) must have at least 2:1 risk-reward ratio
    # Example: if you risk ₹50, your target profit must be at least ₹100
    if prediction["action"] in ["BUY", "SELL"]:
        if prediction["risk_reward_ratio"] < 2:
            return False, "RULE_VIOLATION: Risk Reward must be at least 2:1."

    # Rule B: HOLD means "do nothing" — so the allocation must always be 0%
    # Allocating money to a HOLD recommendation is a contradiction
    if prediction["action"] == "HOLD":
        if prediction["recommended_allocation_pct"] != 0:
            return False, "RULE_VIOLATION: HOLD signals must have 0% allocation."

    # ── All checks passed ─────────────────────────────────────────────────────
    return True, "SYSTEM_PASS"