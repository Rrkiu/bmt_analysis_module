"""Milestone 4: Complete Court Detection API with Overlay and Confidence Scoring

This module provides the complete integration API for court detection, including:
- Automatic detection and calibration
- Court line overlay generation
- Confidence scoring for detection quality
- Verification UI data preparation
"""

import numpy as np
import cv2
from typing import Dict, Optional, Any, Tuple
import logging
from pathlib import Path
import sys

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from modules.court_detection.integration import auto_calibrate_from_image, AutoCalibrationResult
from modules.court_detection.line_generator import CourtLineGenerator
from modules.court_detection.overlay_renderer import CourtOverlayRenderer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DetectionConfidence:
    """Calculate confidence scores for court detection quality"""
    
    @staticmethod
    def calculate_mask_quality(metadata: Dict) -> float:
        """
        Calculate mask quality score (0-1).
        
        Args:
            metadata: Detection metadata from CourtDetector
            
        Returns:
            Score between 0 and 1 (higher is better)
        """
        if not metadata:
            return 0.0
        
        # Mask coverage ratio (higher is better, but too high might indicate issues)
        coverage = metadata.get('mask_coverage_ratio', 0.0)
        
        # Optimal coverage is around 0.05-0.15 (5-15% of image)
        if coverage < 0.02:
            coverage_score = coverage / 0.02  # Penalize very low coverage
        elif coverage <= 0.15:
            coverage_score = 1.0  # Optimal range
        else:
            coverage_score = max(0.0, 1.0 - (coverage - 0.15) / 0.15)  # Penalize too high
        
        return coverage_score
    
    @staticmethod
    def calculate_geometry_quality(corners_image: Dict, image_shape: Tuple[int, int]) -> float:
        """
        Calculate geometric quality score based on corner positions (0-1).
        
        Args:
            corners_image: Dictionary with corner positions {'TL': [x,y], ...}
            image_shape: (height, width) of image
            
        Returns:
            Score between 0 and 1 (higher is better)
        """
        if not corners_image or len(corners_image) != 4:
            return 0.0
        
        H, W = image_shape
        
        # Extract corners
        tl = np.array(corners_image['TL'])
        tr = np.array(corners_image['TR'])
        br = np.array(corners_image['BR'])
        bl = np.array(corners_image['BL'])
        
        scores = []
        
        # 1. Check if corners are within image bounds (with margin)
        margin = 10
        all_corners = [tl, tr, br, bl]
        in_bounds = all([
            margin <= pt[0] <= W - margin and margin <= pt[1] <= H - margin
            for pt in all_corners
        ])
        scores.append(1.0 if in_bounds else 0.5)
        
        # 2. Check if top corners are roughly aligned (y-coordinate)
        top_y_diff = abs(tl[1] - tr[1])
        max_allowed_diff = H * 0.15  # Allow 15% of image height
        y_alignment_score = max(0.0, 1.0 - top_y_diff / max_allowed_diff)
        scores.append(y_alignment_score)
        
        # 3. Check if corners form a reasonable quadrilateral
        # Calculate aspect ratio (width/height)
        top_width = np.linalg.norm(tr - tl)
        bottom_width = np.linalg.norm(br - bl)
        left_height = np.linalg.norm(bl - tl)
        right_height = np.linalg.norm(br - tr)
        
        avg_width = (top_width + bottom_width) / 2
        avg_height = (left_height + right_height) / 2
        
        if avg_height > 0:
            aspect_ratio = avg_width / avg_height
            # Expected aspect ratio for full court: 6.1m / 13.4m ≈ 0.45
            # Allow range 0.3 - 0.7
            if 0.3 <= aspect_ratio <= 0.7:
                aspect_score = 1.0
            else:
                aspect_score = max(0.0, 1.0 - abs(aspect_ratio - 0.45) / 0.45)
            scores.append(aspect_score)
        
        # 4. Check if sides are roughly parallel
        # Left and right sides should have similar slopes
        if left_height > 0 and right_height > 0:
            width_consistency = 1.0 - abs(top_width - bottom_width) / max(top_width, bottom_width)
            height_consistency = 1.0 - abs(left_height - right_height) / max(left_height, right_height)
            scores.append((width_consistency + height_consistency) / 2)
        
        return float(np.mean(scores))
    
    @staticmethod
    def calculate_calibration_quality(pixels_per_meter: float, image_shape: Tuple[int, int]) -> float:
        """
        Calculate calibration quality score (0-1).
        
        Args:
            pixels_per_meter: Calibration scale factor
            image_shape: (height, width) of image
            
        Returns:
            Score between 0 and 1 (higher is better)
        """
        if pixels_per_meter <= 0:
            return 0.0
        
        H, W = image_shape
        
        # Expected range for reasonable calibration
        # For 1080p image with full court: ~30-80 pixels/meter
        # For 720p: ~20-50 pixels/meter
        min_expected = 15
        max_expected = 100
        
        if min_expected <= pixels_per_meter <= max_expected:
            return 1.0
        elif pixels_per_meter < min_expected:
            return pixels_per_meter / min_expected
        else:
            return max(0.0, 1.0 - (pixels_per_meter - max_expected) / max_expected)
    
    @classmethod
    def calculate_overall_confidence(
        cls,
        calibration_result: AutoCalibrationResult,
        image_shape: Tuple[int, int]
    ) -> Dict[str, float]:
        """
        Calculate overall confidence scores.
        
        Args:
            calibration_result: Result from auto_calibrate_from_image
            image_shape: (height, width) of image
            
        Returns:
            Dictionary with confidence scores:
            {
                'mask_quality': float,
                'geometry_quality': float,
                'calibration_quality': float,
                'overall': float
            }
        """
        if not calibration_result.success:
            return {
                'mask_quality': 0.0,
                'geometry_quality': 0.0,
                'calibration_quality': 0.0,
                'overall': 0.0
            }
        
        # Calculate individual scores
        mask_score = cls.calculate_mask_quality(calibration_result.detection_metadata)
        geometry_score = cls.calculate_geometry_quality(
            calibration_result.corners_image,
            image_shape
        )
        calibration_score = cls.calculate_calibration_quality(
            calibration_result.pixels_per_meter,
            image_shape
        )
        
        # Weighted average (geometry is most important)
        weights = {
            'mask': 0.2,
            'geometry': 0.5,
            'calibration': 0.3
        }
        
        overall = (
            mask_score * weights['mask'] +
            geometry_score * weights['geometry'] +
            calibration_score * weights['calibration']
        )
        
        return {
            'mask_quality': float(mask_score),
            'geometry_quality': float(geometry_score),
            'calibration_quality': float(calibration_score),
            'overall': float(overall)
        }


def detect_court_with_overlay(
    image: np.ndarray,
    ensemble_mode: str = 'conservative',
    use_extrapolation: bool = False,
    include_doubles: bool = True,
    overlay_alpha: float = 1.0,
    draw_corners: bool = True,
    return_separate_images: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Complete court detection API with overlay and confidence scoring.
    
    This is the main Milestone 4 API that provides:
    - Automatic court detection and calibration
    - Court line overlay visualization
    - Confidence scoring for quality assessment
    - Verification UI data
    
    Args:
        image: BGR image as numpy array (H, W, 3)
        ensemble_mode: Mask generation mode ('conservative', 'moderate', 'aggressive')
        use_extrapolation: Enable line extrapolation for better endpoint estimation
        include_doubles: Include doubles court lines (sidelines, long service)
        overlay_alpha: Transparency for overlay (0.0 = transparent, 1.0 = opaque)
        draw_corners: Whether to draw corner markers on overlay
        return_separate_images: If True, return both original and overlay separately
        **kwargs: Additional parameters passed to detection pipeline
        
    Returns:
        Dictionary containing:
        {
            'success': bool,
            'overlay_image': np.ndarray,  # Image with court lines overlaid
            'original_image': np.ndarray,  # Original image (if return_separate_images=True)
            'confidence': {
                'mask_quality': float,
                'geometry_quality': float,
                'calibration_quality': float,
                'overall': float
            },
            'corners': {
                'TL': [x, y],
                'TR': [x, y],
                'BR': [x, y],
                'BL': [x, y]
            },
            'calibration': {
                'homography_matrix': list,
                'pixels_per_meter': float,
                'court_corners_world': list
            },
            'lines': {
                'line_name': [[x1, y1], [x2, y2], ...],
                ...
            },
            'metadata': {
                'image_shape': [height, width],
                'ensemble_mode': str,
                'detection_metadata': dict
            },
            'error': str  # Only present if success=False
        }
        
    Example:
        >>> result = detect_court_with_overlay(image)
        >>> if result['success']:
        >>>     cv2.imshow('Court Detection', result['overlay_image'])
        >>>     print(f"Confidence: {result['confidence']['overall']:.2%}")
    """
    logger.info("Starting detect_court_with_overlay")
    
    # Validate input
    if image is None or image.size == 0:
        return {
            'success': False,
            'error': 'Invalid input image'
        }
    
    H, W = image.shape[:2]
    image_shape = (H, W)
    
    try:
        # Step 1: Auto-calibration (detection + calibration)
        logger.info("Step 1/4: Running auto-calibration...")
        calibration_result = auto_calibrate_from_image(
            image=image,
            ensemble_mode=ensemble_mode,
            use_extrapolation=use_extrapolation,
            image_shape=image_shape,
            **kwargs
        )
        
        if not calibration_result.success:
            return {
                'success': False,
                'error': calibration_result.data.get('error', 'Auto-calibration failed')
            }
        
        # Step 2: Calculate confidence scores
        logger.info("Step 2/4: Calculating confidence scores...")
        confidence = DetectionConfidence.calculate_overall_confidence(
            calibration_result,
            image_shape
        )
        
        # Step 3: Generate court lines
        logger.info("Step 3/4: Generating court lines...")
        generator = CourtLineGenerator(court_type='singles')
        world_lines = generator.generate_all_lines(
            include_net=True,
            include_doubles=include_doubles
        )
        styles = generator.get_line_styles()
        
        # Step 4: Render overlay
        logger.info("Step 4/4: Rendering overlay...")
        renderer = CourtOverlayRenderer(calibration_result.homography_matrix)
        overlay_image = renderer.render(
            image=image,
            world_lines=world_lines,
            styles=styles,
            alpha=overlay_alpha,
            draw_corners=draw_corners,
            detected_corners=calibration_result.corners_image
        )
        
        # Prepare result
        result = {
            'success': True,
            'overlay_image': overlay_image,
            'confidence': confidence,
            'corners': calibration_result.corners_image,
            'calibration': {
                'homography_matrix': calibration_result.homography_matrix,
                'pixels_per_meter': calibration_result.pixels_per_meter,
                'court_corners_world': calibration_result.corners_world
            },
            'lines': world_lines,
            'metadata': {
                'image_shape': [H, W],
                'ensemble_mode': ensemble_mode,
                'use_extrapolation': use_extrapolation,
                'include_doubles': include_doubles,
                'detection_metadata': calibration_result.detection_metadata
            }
        }
        
        # Optionally include original image
        if return_separate_images:
            result['original_image'] = image.copy()
        
        logger.info(f"Detection complete. Confidence: {confidence['overall']:.2%}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in detect_court_with_overlay: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


# Convenience function for quick testing
def quick_detect(image_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick detection from image file path.
    
    Args:
        image_path: Path to input image
        output_path: Optional path to save overlay image
        
    Returns:
        Detection result dictionary
    """
    image = cv2.imread(image_path)
    if image is None:
        return {
            'success': False,
            'error': f'Failed to load image: {image_path}'
        }
    
    result = detect_court_with_overlay(image)
    
    if result['success'] and output_path:
        cv2.imwrite(output_path, result['overlay_image'])
        logger.info(f"Saved overlay to: {output_path}")
    
    return result


if __name__ == "__main__":
    # Simple CLI test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python api_integration.py <image_path> [output_path]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = quick_detect(image_path, output_path)
    
    if result['success']:
        print("\n" + "="*70)
        print("✅ Court Detection Successful")
        print("="*70)
        print(f"\nConfidence Scores:")
        for key, value in result['confidence'].items():
            print(f"  {key}: {value:.2%}")
        print(f"\nCorners:")
        for corner, pos in result['corners'].items():
            print(f"  {corner}: ({pos[0]:.1f}, {pos[1]:.1f})")
        print(f"\nCalibration:")
        print(f"  Pixels/meter: {result['calibration']['pixels_per_meter']:.2f}")
        print("="*70)
    else:
        print(f"\n❌ Detection Failed: {result['error']}")
