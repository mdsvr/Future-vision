"""
confidence_model.py — Confidence Model Interface
=================================================
Thin adapter for the fusion_engine package structure.
All logic lives in ../confidence.py.
"""
from confidence import compute_confidence, REGIME_WEIGHTS, DEFAULT_WEIGHTS

__all__ = ["compute_confidence", "REGIME_WEIGHTS", "DEFAULT_WEIGHTS"]
