"""4-point court corner detection from line mask

This module provides the PointDetector class for detecting 4 corner points
(TL, TR, BR, BL) from court line masks using bottom-up sideline extraction.

Implementation: Wrapper around legacy/pl_1_ransac_cld_bup_ll_v7.py to ensure
100% identical results. Will be refactored to pure implementation in future.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
import sys

# Import legacy code
legacy_path = Path(__file__).parent.parent / 'legacy'
sys.path.insert(0, str(legacy_path))

# Import all required functions from legacy code
from pl_1_ransac_cld_bup_ll_v7 import (
    build_sideline_support_mask,
    remove_horizontal_components,
    get_ransac_points,
    bottom_up_sideline_extraction,
    enforce_paired_top_constraint_line_equation,
    overlay_points,
    draw_line_on_image,
    draw_point
)

# Remove from sys.path to avoid conflicts
sys.path.remove(str(legacy_path))

from .utils import save_image, to_bgr


class PointDetectorArgs:
    """
    Parameter container matching legacy argparse defaults.
    All parameters set to match --no_extrapolation mode.
    """
    def __init__(self, use_extrapolation=False, save_intermediate=False):
        # Preprocessing
        self.open_ks = 0
        self.dilate_ks = 3
        self.use_edge_points = False
        
        # Horizontal removal
        self.horiz_kernel_ratio = 0.25
        self.horiz_iter = 1
        self.horiz_central_band_only = False
        self.horiz_band_y0_ratio = 0.40
        self.horiz_band_y1_ratio = 0.70
        
        # Point extraction
        self.max_points = 120000
        
        # Bottom-up extraction
        self.bottom_ratio = 0.25
        self.seed_y_bin = 10
        self.seed_tolerance = 10.0
        self.extend_dist_th = 8.0
        self.extend_x_tolerance = 15.0
        self.continuity_th = 25.0
        self.extend_y_bin = 15
        
        # Linearity filter
        self.k_neighbors = 12
        self.linearity_th = 4.0
        
        # Final RANSAC
        self.final_ransac_dist_th = 3.0
        self.final_ransac_iter = 500
        
        # Endpoint computation
        self.use_line_equation = True
        self.use_extrapolation = use_extrapolation  # KEY: False by default (--no_extrapolation)
        self.top_margin = 0.02
        self.bot_margin = 0.02
        self.max_top_y_diff = 90.0
        
        # Legacy (not used when use_line_equation=True)
        self.top_pct = 3.0
        self.bot_pct = 97.0
        
        # Internal
        self.save_intermediate = save_intermediate


class PointDetector:
    """
    Detect 4 corner points (TL, TR, BR, BL) from court line mask.
    
    Uses bottom-up sideline extraction with RANSAC fitting.
    
    This is a wrapper around legacy code to ensure 100% identical results.
    Parameters match legacy defaults with --no_extrapolation flag.
    
    Example:
        >>> detector = PointDetector(use_extrapolation=False)
        >>> corners = detector.detect(mask, original_img)
        >>> print(corners['TL'], corners['TR'], corners['BR'], corners['BL'])
    """
    
    def __init__(self,
                 use_extrapolation: bool = False,
                 bottom_ratio: float = 0.25,
                 final_ransac_dist_th: float = 3.0,
                 save_intermediate: bool = False,
                 **kwargs):
        """
        Initialize point detector.
        
        Args:
            use_extrapolation: Extrapolate lines beyond detected points (default: False)
            bottom_ratio: Use bottom X% for seed extraction (default: 0.25)
            final_ransac_dist_th: Distance threshold for final RANSAC (default: 3.0)
            save_intermediate: Save intermediate detection results
            **kwargs: Additional parameters (currently unused, for future compatibility)
        """
        self.use_extrapolation = use_extrapolation
        self.save_intermediate = save_intermediate
        
        # Create args object with legacy defaults
        self.args = PointDetectorArgs(
            use_extrapolation=use_extrapolation,
            save_intermediate=save_intermediate
        )
        
        # Override specific parameters if provided
        self.args.bottom_ratio = bottom_ratio
        self.args.final_ransac_dist_th = final_ransac_dist_th
        
        # Apply any additional kwargs
        for key, value in kwargs.items():
            if hasattr(self.args, key):
                setattr(self.args, key, value)
    
    def detect(self,
               mask: np.ndarray,
               original_img: Optional[np.ndarray] = None,
               out_dir: Optional[Path] = None) -> Dict[str, np.ndarray]:
        """
        Detect 4 corner points from court line mask.
        
        Wrapper around legacy estimate_4pts_from_mask() function.
        
        Args:
            mask: Binary mask (0/255) of court lines
            original_img: Original image for visualization (optional)
            out_dir: Output directory for intermediate results (optional)
            
        Returns:
            Dictionary with keys: 'TL', 'TR', 'BR', 'BL'
            Each value is np.array([x, y], dtype=np.float32)
        """
        H, W = mask.shape[:2]
        
        # Use original image for visualization if provided, otherwise use mask
        if original_img is not None:
            base_vis = original_img
        else:
            base_vis = to_bgr(mask)
        
        # Call legacy function
        from pl_1_ransac_cld_bup_ll_v7 import estimate_4pts_from_mask
        
        pts_dict = estimate_4pts_from_mask(
            mask255=mask,
            base_vis=base_vis,
            out_dir=out_dir,
            args=self.args
        )
        
        return pts_dict

