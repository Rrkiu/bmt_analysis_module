"""Court line mask generation from RGB image using multi-colorspace analysis

This module provides the MaskGenerator class for extracting court line masks
from RGB images using ensemble methods across multiple colorspaces (HSV, YCbCr, LAB).

Implementation extracted from legacy/s_analysis_cp_pl.py (lines 833-910)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict


class MaskGenerator:
    """
    Generate court line mask using multi-colorspace analysis.
    
    Uses conservative ensemble mode: HSV AND YCbCr AND LAB
    This provides high precision for white line detection.
    
    Thresholds (from legacy code):
    - HSV: S < 90, V > 150 (low saturation, high value = white)
    - YCbCr: Y > 200 (high luminance = bright)
    - LAB: L > 200 (high lightness = white)
    
    Example:
        >>> generator = MaskGenerator()
        >>> mask = generator.generate(bgr_image)
        >>> # mask is binary 0/255 where 255 = detected court lines
    """
    
    def __init__(self, 
                 ensemble_mode: str = 'conservative',
                 save_intermediate: bool = False):
        """
        Initialize mask generator.
        
        Args:
            ensemble_mode: Only 'conservative' is implemented (HSV AND YCbCr AND LAB)
            save_intermediate: Save intermediate analysis results
        """
        if ensemble_mode != 'conservative':
            raise ValueError(f"Only 'conservative' mode is implemented, got: {ensemble_mode}")
        
        self.ensemble_mode = ensemble_mode
        self.save_intermediate = save_intermediate
        
        # Thresholds from legacy code (lines 852-854)
        # All modes use same thresholds, only operation differs
        self.s_max = 90
        self.v_min = 150
        self.y_min = 200
        self.l_min = 200
    
    def generate(self, 
                 bgr_img: np.ndarray,
                 out_dir: Optional[Path] = None) -> np.ndarray:
        """
        Generate court line mask from BGR image.
        
        Implementation from legacy/s_analysis_cp_pl.py lines 840-883
        
        Args:
            bgr_img: Input BGR image (H, W, 3)
            out_dir: Optional output directory for intermediate results
            
        Returns:
            Binary mask (0/255) of detected court lines
            Shape: (H, W) uint8
        """
        # Step 1: Convert to color spaces (lines 840-842)
        hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
        ycbcr = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
        lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)
        
        # Step 2: Extract channels (lines 844-846)
        _, s_ch, v_ch = cv2.split(hsv)
        y_ch, _, _ = cv2.split(ycbcr)
        l_ch, _, _ = cv2.split(lab)
        
        # Step 3: Apply thresholds (line 878-880)
        # Note: astype(np.uint8) converts True/False to 1/0
        mask_hsv = ((s_ch < self.s_max) & (v_ch > self.v_min)).astype(np.uint8)
        mask_ycbcr = (y_ch > self.y_min).astype(np.uint8)
        mask_lab = (l_ch > self.l_min).astype(np.uint8)
        
        # Step 4: Conservative ensemble - AND operation (line 883)
        mask_final = (mask_hsv & mask_ycbcr & mask_lab) * 255
        
        # Step 5: Save intermediate results if requested
        if self.save_intermediate and out_dir is not None:
            from .utils import save_image
            
            # Save individual channel masks
            save_image(out_dir, "mask_hsv", mask_hsv * 255)
            save_image(out_dir, "mask_ycbcr", mask_ycbcr * 255)
            save_image(out_dir, "mask_lab", mask_lab * 255)
            
            # Save final ensemble mask (this is the key output!)
            save_image(out_dir, "mask_ensemble_conservative", mask_final)
        
        return mask_final

