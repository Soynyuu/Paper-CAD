"""
CityGML to STEP conversion module (refactored).

Public API preserving exact compatibility with original citygml_to_step.py.
"""

# Delegate to original implementation for backward compatibility
from ..citygml_to_step import export_step_from_citygml

__all__ = ["export_step_from_citygml"]
