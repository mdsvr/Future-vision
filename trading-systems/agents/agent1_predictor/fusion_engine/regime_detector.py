"""
regime_detector.py — Regime Detection Interface
================================================
Thin adapter for the fusion_engine package structure.
All logic lives in ../regime.py.
"""
from regime import classify_regime, calculate_hurst_exponent

__all__ = ["classify_regime", "calculate_hurst_exponent"]
