"""Core court detection logic - I/O agnostic

This module contains the pure detection algorithm without any file I/O dependencies.
Can be used by both API and test pipeline.

The CourtDetector class provides a clean interface for court corner detection
that works entirely in memory, making it suitable for API integration.
"""

import numpy as np
from typing import Dict, Optional, Tuple, Any
import logging

from modules import MaskGenerator, PointDetector

# Configure logging
logger = logging.getLogger(__name__)


class CourtDetector:
    """
    Core court detection class - no file I/O dependencies.
    
    This class encapsulates the entire detection pipeline in a memory-only
    implementation, making it suitable for API integration and testing.
    
    Example:
        >>> detector = CourtDetector(ensemble_mode='conservative')
        >>> result = detector.detect(image_array)
        >>> corners = result['corners']
        >>> print(f"TL: {corners['TL']}")
    """
    
    def __init__(self, 
                 ensemble_mode: str = 'conservative',
                 use_extrapolation: bool = False,
                 **kwargs):
        """
        Initialize detector with configuration.
        
        Args:
            ensemble_mode: Mask generation mode
                - 'conservative': High precision, may miss some lines
                - 'moderate': Balanced precision and recall
                - 'aggressive': High recall, may include noise
            use_extrapolation: Enable line extrapolation for endpoint detection
            **kwargs: Additional parameters passed to modules
                - bottom_ratio: Ratio of bottom region for seed extraction
                - final_ransac_dist_th: Distance threshold for RANSAC
                - etc. (see modules for full list)
        """
        if ensemble_mode not in ['conservative', 'moderate', 'aggressive']:
            raise ValueError(f"Invalid ensemble_mode: {ensemble_mode}. "
                           f"Must be one of: conservative, moderate, aggressive")
        
        self.ensemble_mode = ensemble_mode
        self.use_extrapolation = use_extrapolation
        self.kwargs = kwargs
        
        logger.info(f"Initializing CourtDetector: mode={ensemble_mode}, "
                   f"extrapolation={use_extrapolation}")
        
        # Initialize modules (never save intermediate results in core)
        self.mask_generator = MaskGenerator(
            ensemble_mode=ensemble_mode,
            save_intermediate=False
        )
        
        self.point_detector = PointDetector(
            use_extrapolation=use_extrapolation,
            save_intermediate=False,
            **{k: v for k, v in kwargs.items() 
               if k in ['bottom_ratio', 'final_ransac_dist_th', 'seed_y_bin', 
                       'seed_tolerance', 'extend_dist_th', 'continuity_th']}
        )
    
    def detect(self, 
               image: np.ndarray,
               return_mask: bool = True,
               return_metadata: bool = True) -> Dict[str, Any]:
        """
        Detect court corners from image array.
        
        Args:
            image: BGR image as numpy array (H, W, 3)
            return_mask: Include binary mask in results
            return_metadata: Include detection metadata in results
            
        Returns:
            Dictionary with detection results:
            {
                'corners': {
                    'TL': [x, y],  # Top-Left
                    'TR': [x, y],  # Top-Right
                    'BR': [x, y],  # Bottom-Right
                    'BL': [x, y]   # Bottom-Left
                },
                'mask': np.ndarray (optional, if return_mask=True),
                'metadata': {
                    'image_size': (W, H),
                    'ensemble_mode': str,
                    'use_extrapolation': bool
                } (optional, if return_metadata=True)
            }
            
        Raises:
            ValueError: If image is invalid (None, empty, or wrong shape)
            RuntimeError: If detection fails
        """
        # Validate input
        self._validate_image(image)
        
        H, W = image.shape[:2]
        logger.info(f"Starting detection on image: {W}x{H}")
        
        try:
            # Step 1: Generate mask
            logger.debug("Step 1: Generating court line mask...")
            mask = self.mask_generator.generate(image, out_dir=None)
            logger.debug(f"Mask generated: {mask.shape}, "
                        f"white pixels: {np.sum(mask > 0)}")
            
            # Step 2: Detect corners
            logger.debug("Step 2: Detecting corner points...")
            corners = self.point_detector.detect(mask, image, out_dir=None)
            logger.debug(f"Corners detected: {list(corners.keys())}")
            
            # Step 3: Build result dictionary
            result = {
                'corners': corners
            }
            
            if return_mask:
                result['mask'] = mask
            
            if return_metadata:
                result['metadata'] = {
                    'image_size': (W, H),
                    'ensemble_mode': self.ensemble_mode,
                    'use_extrapolation': self.use_extrapolation,
                    'mask_white_pixels': int(np.sum(mask > 0)),
                    'mask_coverage_ratio': float(np.sum(mask > 0) / (H * W))
                }
            
            logger.info("Detection completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Detection failed: {e}", exc_info=True)
            raise RuntimeError(f"Court detection failed: {e}") from e
    
    def _validate_image(self, image: np.ndarray):
        """
        Validate input image.
        
        Args:
            image: Input image array
            
        Raises:
            ValueError: If image is invalid
        """
        if image is None:
            raise ValueError("Image is None")
        
        if not isinstance(image, np.ndarray):
            raise ValueError(f"Image must be numpy array, got {type(image)}")
        
        if image.size == 0:
            raise ValueError("Image is empty (size=0)")
        
        if len(image.shape) != 3:
            raise ValueError(f"Image must be 3D (H, W, C), got shape: {image.shape}")
        
        if image.shape[2] != 3:
            raise ValueError(f"Image must have 3 channels (BGR), got {image.shape[2]} channels")
        
        H, W = image.shape[:2]
        if H < 100 or W < 100:
            raise ValueError(f"Image too small: {W}x{H}. Minimum size is 100x100")
        
        logger.debug(f"Image validation passed: {W}x{H}, dtype={image.dtype}")
    
    def __repr__(self):
        return (f"CourtDetector(ensemble_mode='{self.ensemble_mode}', "
                f"use_extrapolation={self.use_extrapolation})")


def detect_court(image: np.ndarray,
                 ensemble_mode: str = 'conservative',
                 use_extrapolation: bool = False,
                 **kwargs) -> Dict[str, Any]:
    """
    Convenience function for one-shot detection.
    
    Args:
        image: BGR image as numpy array
        ensemble_mode: Mask generation mode
        use_extrapolation: Enable line extrapolation
        **kwargs: Additional parameters
        
    Returns:
        Detection results dictionary
        
    Example:
        >>> import cv2
        >>> image = cv2.imread('court.png')
        >>> result = detect_court(image)
        >>> print(result['corners']['TL'])
    """
    detector = CourtDetector(
        ensemble_mode=ensemble_mode,
        use_extrapolation=use_extrapolation,
        **kwargs
    )
    return detector.detect(image)
