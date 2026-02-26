import json
import uuid
from datetime import datetime
from jsonschema import validate, ValidationError

import os

# Locate the standardized JSON schema
SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__),
    "schema",
    "agent1_prediction.schema.json"
)

with open(SCHEMA_PATH, "r") as f:
    SCHEMA = json.load(f)


def validate_prediction(prediction: dict):
    """
    Two-stage validation for all Agent 1 outputs.
    1. Schema Validation: Checks structure, types, and required fields.
    2. Domain Validation: Checks logical trading rules (RR ratio, Allocation).
    """
    # Stage 1: Structure & Typing
    try:
        validate(instance=prediction, schema=SCHEMA)
    except ValidationError as e:
        return False, f"JSON_SCHEMA_ERROR: {e.message}"

    # Stage 2: Hard Domain Business Rules
    
    # Check A: Risk-Reward Ratio enforcement for active trades
    if prediction["action"] in ["BUY", "SELL"]:
        if prediction["risk_reward_ratio"] < 2:
            return False, "RULE_VIOLATION: Risk Reward must be at least 2:1."

    # Check B: Consistency check for HOLD status
    if prediction["action"] == "HOLD":
        if prediction["recommended_allocation_pct"] != 0:
            return False, "RULE_VIOLATION: HOLD signals must have 0% allocation."

    return True, "SYSTEM_PASS"