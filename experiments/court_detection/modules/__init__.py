"""Court detection modules

This package contains core modules for badminton court detection:
- mask_generator: Generate court line masks from RGB images
- point_detector: Detect 4 corner points from line masks
- utils: Common utility functions
"""

from .mask_generator import MaskGenerator
from .point_detector import PointDetector
from . import utils

__all__ = ['MaskGenerator', 'PointDetector', 'utils']
__version__ = '1.0.0'
