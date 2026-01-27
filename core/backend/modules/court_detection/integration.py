"""Integration layer between court detection and calibration

This module provides high-level functions that combine automatic court detection
with the existing calibration system, creating a seamless pipeline from image
to fully calibrated court coordinates.
"""

import numpy as np
from typing import Dict, Optional, Any, Tuple
import logging
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from .core_detector import CourtDetector
from ..calibration import CalibrationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoCalibrationResult:
    """Result container for auto-calibration with convenience methods"""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.success = data.get('success', False)
    
    @property
    def corners_image(self) -> Optional[Dict[str, list]]:
        """Get detected corners in image coordinates"""
        return self.data.get('corners_image')
    
    @property
    def corners_world(self) -> Optional[list]:
        """Get court corners in world coordinates"""
        return self.data.get('court_corners_world')
    
    @property
    def homography_matrix(self) -> Optional[list]:
        """Get homography transformation matrix"""
        return self.data.get('homography_matrix')
    
    @property
    def pixels_per_meter(self) -> Optional[float]:
        """Get pixel to meter ratio"""
        return self.data.get('pixels_per_meter')
    
    @property
    def detection_metadata(self) -> Optional[Dict]:
        """Get detection metadata (mask quality, etc.)"""
        return self.data.get('detection_metadata')
    
    @property
    def calibration_data(self) -> Optional[Dict]:
        """Get full calibration data"""
        return self.data.get('calibration_data')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return self.data
    
    def __repr__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return f"AutoCalibrationResult(status={status})"


def auto_calibrate_from_image(
    image: np.ndarray,
    ensemble_mode: str = 'conservative',
    use_extrapolation: bool = False,
    image_shape: Optional[Tuple[int, int]] = None,
    **kwargs
) -> AutoCalibrationResult:
    """
    Automatic court detection and calibration from image.
    
    This is the main integration function that combines:
    1. Automatic corner detection (CourtDetector)
    2. Calibration computation (CalibrationService)
    
    Args:
        image: BGR image as numpy array (H, W, 3)
        ensemble_mode: Mask generation mode
            - 'conservative': High precision (default)
            - 'moderate': Balanced
            - 'aggressive': High recall
        use_extrapolation: Enable line extrapolation for better endpoint estimation
        image_shape: Optional (height, width) tuple, auto-detected if None
        **kwargs: Additional parameters passed to CourtDetector
        
    Returns:
        AutoCalibrationResult containing:
        {
            'success': bool,
            'corners_image': {
                'TL': [x, y],
                'TR': [x, y],
                'BR': [x, y],
                'BL': [x, y]
            },
            'corners_image_list': [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],  # For CalibrationService
            'court_corners_world': [...],  # World coordinates
            'homography_matrix': [...],
            'inverse_homography_matrix': [...],
            'pixels_per_meter': float,
            'image_shape': (H, W),
            'detection_metadata': {...},  # From CourtDetector
            'calibration_data': {...},    # Full calibration result
            'error': str (only if success=False),
            'error_stage': str (only if success=False)
        }
        
    Example:
        >>> import cv2
        >>> img = cv2.imread('court.jpg')
        >>> result = auto_calibrate_from_image(img)
        >>> if result.success:
        >>>     print(f"Corners: {result.corners_image}")
        >>>     print(f"Homography: {result.homography_matrix}")
        >>> else:
        >>>     print(f"Failed: {result.data['error']}")
    """
    logger.info(f"Starting auto-calibration: mode={ensemble_mode}, extrapolation={use_extrapolation}")
    
    try:
        # Step 1: Validate image
        if image is None or image.size == 0:
            return AutoCalibrationResult({
                'success': False,
                'error': 'Invalid image: None or empty',
                'error_stage': 'validation'
            })
        
        # Get image shape
        if image_shape is None:
            H, W = image.shape[:2]
            image_shape = (H, W)
        else:
            H, W = image_shape
        
        logger.info(f"Image shape: {W}x{H}")
        
        # Step 2: Detect court corners
        logger.info("Step 1/2: Detecting court corners...")
        detector = CourtDetector(
            ensemble_mode=ensemble_mode,
            use_extrapolation=use_extrapolation,
            **kwargs
        )
        
        detection_result = detector.detect(
            image,
            return_mask=False,  # Don't need mask for calibration
            return_metadata=True
        )
        
        corners_dict = detection_result['corners']
        detection_metadata = detection_result.get('metadata', {})
        
        logger.info(f"Corners detected: {list(corners_dict.keys())}")
        
        # Step 3: Convert corners to CalibrationService format
        # CalibrationService expects: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] in TL, TR, BR, BL order
        corners_list = [
            corners_dict['TL'],
            corners_dict['TR'],
            corners_dict['BR'],
            corners_dict['BL']
        ]
        
        logger.info(f"Corners list: {corners_list}")
        
        # Step 4: Perform calibration
        logger.info("Step 2/2: Computing calibration...")
        calibration_service = CalibrationService()
        
        calibration_result = calibration_service.calibrate_from_corners(
            court_corners_image=corners_list,
            image_shape=image_shape
        )
        
        if not calibration_result.get('success'):
            error_msg = calibration_result.get('error', 'Unknown calibration error')
            logger.error(f"Calibration failed: {error_msg}")
            return AutoCalibrationResult({
                'success': False,
                'error': error_msg,
                'error_stage': 'calibration',
                'corners_image': corners_dict,
                'detection_metadata': detection_metadata
            })
        
        logger.info("Calibration successful")
        
        # Step 5: Build comprehensive result
        result_data = {
            'success': True,
            'corners_image': corners_dict,  # Dict format for easy access
            'corners_image_list': corners_list,  # List format for compatibility
            'court_corners_world': calibration_result['court_corners_world'],
            'homography_matrix': calibration_result['homography_matrix'],
            'pixels_per_meter': calibration_result['pixels_per_meter'],
            'image_shape': image_shape,
            'detection_metadata': detection_metadata,
            'calibration_data': calibration_result  # Full calibration result
        }
        
        logger.info(f"Auto-calibration completed successfully (pixels_per_meter: {result_data['pixels_per_meter']:.2f})")
        
        return AutoCalibrationResult(result_data)
        
    except Exception as e:
        logger.error(f"Auto-calibration failed with exception: {e}", exc_info=True)
        return AutoCalibrationResult({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'error_stage': 'unknown'
        })


def validate_corners(corners: Dict[str, list]) -> Tuple[bool, str]:
    """
    Validate detected corners for geometric consistency.
    
    Args:
        corners: Dictionary with TL, TR, BR, BL keys
        
    Returns:
        (is_valid, message) tuple
    """
    required_keys = ['TL', 'TR', 'BR', 'BL']
    
    # Check all keys present
    if not all(key in corners for key in required_keys):
        missing = [key for key in required_keys if key not in corners]
        return False, f"Missing corner keys: {missing}"
    
    # Check all values are valid coordinates
    for key, point in corners.items():
        if not isinstance(point, (list, tuple, np.ndarray)):
            return False, f"Corner {key} is not a valid coordinate type"
        if len(point) != 2:
            return False, f"Corner {key} does not have 2 coordinates"
        if not all(isinstance(v, (int, float, np.number)) for v in point):
            return False, f"Corner {key} contains non-numeric values"
    
    # Check geometric validity (rough quadrilateral check)
    points = np.array([corners[k] for k in required_keys], dtype=np.float32)
    
    # Check if points form a valid quadrilateral (non-zero area)
    area = cv2.contourArea(points)
    if area < 1000:  # Minimum area threshold
        return False, f"Court area too small: {area:.0f} pixels"
    
    return True, "Valid corners"


# Convenience function for backward compatibility
def detect_and_calibrate(
    image: np.ndarray,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience wrapper that returns dict instead of AutoCalibrationResult.
    
    Args:
        image: BGR image
        **kwargs: Parameters for auto_calibrate_from_image
        
    Returns:
        Dictionary with calibration results
    """
    result = auto_calibrate_from_image(image, **kwargs)
    return result.to_dict()


# Import cv2 for validation
import cv2


if __name__ == "__main__":
    # Simple test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python integration.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    print(f"\nTesting auto-calibration with: {image_path}\n")
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image: {image_path}")
        sys.exit(1)
    
    result = auto_calibrate_from_image(img, ensemble_mode='conservative')
    
    if result.success:
        print("✅ Auto-calibration SUCCESS!")
        print(f"\nCorners (image coordinates):")
        for key, point in result.corners_image.items():
            print(f"  {key}: ({point[0]:.1f}, {point[1]:.1f})")
        print(f"\nPixels per meter: {result.pixels_per_meter:.2f}")
        print(f"Detection quality: {result.detection_metadata.get('mask_coverage_ratio', 0):.3f}")
    else:
        print("❌ Auto-calibration FAILED")
        print(f"Error: {result.data.get('error')}")
        print(f"Stage: {result.data.get('error_stage')}")
