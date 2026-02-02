"""Config package initialization"""

from .default_config import (
    Config,
    DetectionConfig,
    TrackingConfig,
    VisualizationConfig,
)

__all__ = [
    'Config',
    'DetectionConfig',
    'TrackingConfig',
    'VisualizationConfig',
]
