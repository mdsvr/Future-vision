"""
fusion_engine — Signal fusion and confidence modeling package.
Re-exports from the flat confidence.py and regime.py modules
to provide the modular folder structure described in the architecture doc.
"""
from confidence import compute_confidence
from regime import classify_regime

__all__ = ["compute_confidence", "classify_regime"]
