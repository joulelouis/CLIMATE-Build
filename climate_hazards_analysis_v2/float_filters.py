
"""
DEPRECATED: This module is deprecated and consolidated into climate_hazards_analysis.templatetags.common_filters

Use climate_hazards_analysis.templatetags.common_filters instead.
"""

# Import the consolidated function for backward compatibility
from climate_hazards_analysis.templatetags.common_filters import to_float, register

# Add deprecation warning
import warnings
warnings.warn(
    "climate_hazards_analysis_v2.float_filters is deprecated. "
    "Use climate_hazards_analysis.templatetags.common_filters instead.",
    DeprecationWarning,
    stacklevel=2
)