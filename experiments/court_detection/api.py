"""API interface for court detection

Designed for integration with backend services.
Accepts numpy arrays, returns dictionaries.
Optionally saves debug output to storage directory.

This module provides a production-ready API interface that:
- Works entirely in memory (no mandatory file I/O)
- Returns structured JSON-serializable results
- Optionally saves debug output when requested
- Includes comprehensive error handling
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Dict, Optional, Any
import logging
from datetime import datetime
import json

from core_detector import CourtDetector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_court_api(image: np.ndarray,
                     ensemble_mode: str = 'conservative',
                     use_extrapolation: bool = False,
                     debug: bool = False,
                     debug_storage_root: str = '/mnt/b/cd_p/bmt_demo/core/storage',
                     **kwargs) -> Dict[str, Any]:
    """
    API endpoint for court detection.
    
    This is the main entry point for API integration. It accepts a numpy array
    and returns a dictionary with detection results. File I/O only occurs when
    debug=True.
    
    Args:
        image: BGR image as numpy array (H, W, 3)
        ensemble_mode: Mask generation mode
            - 'conservative': High precision (default)
            - 'moderate': Balanced
            - 'aggressive': High recall
        use_extrapolation: Enable line extrapolation for better endpoint estimation
        debug: If True, save debug images to storage directory
        debug_storage_root: Root directory for debug output (only used if debug=True)
        **kwargs: Additional parameters passed to detector
        
    Returns:
        {
            'success': bool,
            'corners': {
                'TL': [x, y],
                'TR': [x, y],
                'BR': [x, y],
                'BL': [x, y]
            },
            'metadata': {
                'image_size': [W, H],
                'ensemble_mode': str,
                'use_extrapolation': bool,
                ...
            },
            'debug_path': str (only if debug=True and success=True),
            'error': str (only if success=False),
            'error_type': str (only if success=False)
        }
    
    Example:
        >>> import cv2
        >>> img = cv2.imread('court.png')
        >>> result = detect_court_api(img)
        >>> if result['success']:
        >>>     corners = result['corners']
        >>>     print(f"TL: {corners['TL']}")
        >>> else:
        >>>     print(f"Error: {result['error']}")
        
        >>> # With debug mode
        >>> result = detect_court_api(img, debug=True)
        >>> if result['success']:
        >>>     print(f"Debug saved to: {result['debug_path']}")
    """
    start_time = datetime.now()
    
    logger.info(f"API call started: ensemble={ensemble_mode}, "
                f"extrapolation={use_extrapolation}, debug={debug}")
    
    try:
        # Create detector
        detector = CourtDetector(
            ensemble_mode=ensemble_mode,
            use_extrapolation=use_extrapolation,
            **kwargs
        )
        
        # Run detection
        detection_result = detector.detect(
            image,
            return_mask=debug,  # Only return mask if debug mode
            return_metadata=True
        )
        
        # Convert numpy arrays to lists for JSON serialization
        corners_serializable = {
            k: v.tolist() if isinstance(v, np.ndarray) else list(v)
            for k, v in detection_result['corners'].items()
        }
        
        # Prepare response
        response = {
            'success': True,
            'corners': corners_serializable,
            'metadata': detection_result['metadata']
        }
        
        # Add processing time
        elapsed = (datetime.now() - start_time).total_seconds()
        response['metadata']['processing_time_seconds'] = round(elapsed, 3)
        
        # Debug mode: save to storage
        if debug:
            try:
                debug_path = _save_debug_output(
                    image=image,
                    mask=detection_result.get('mask'),
                    corners=detection_result['corners'],
                    metadata=detection_result['metadata'],
                    storage_root=debug_storage_root
                )
                response['debug_path'] = str(debug_path)
                logger.info(f"Debug output saved to: {debug_path}")
            except Exception as debug_error:
                logger.warning(f"Failed to save debug output: {debug_error}")
                response['debug_warning'] = f"Debug save failed: {debug_error}"
        
        logger.info(f"Detection successful (took {elapsed:.3f}s)")
        return response
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"Detection failed after {elapsed:.3f}s: {e}", exc_info=True)
        
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'processing_time_seconds': round(elapsed, 3)
        }


def _save_debug_output(image: np.ndarray,
                       mask: Optional[np.ndarray],
                       corners: Dict[str, np.ndarray],
                       metadata: Dict[str, Any],
                       storage_root: str) -> Path:
    """
    Save debug output to storage directory.
    
    Creates a timestamped directory with:
    - Original image
    - Generated mask
    - Visualization with corners
    - Corner coordinates (JSON)
    - Metadata (JSON)
    
    Args:
        image: Original image
        mask: Generated mask (can be None)
        corners: Detected corners
        metadata: Detection metadata
        storage_root: Root storage directory
        
    Returns:
        Path to debug directory
    """
    # Create timestamped directory with milliseconds for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    debug_dir = Path(storage_root) / f"court_detection_{timestamp}"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    logger.debug(f"Saving debug output to: {debug_dir}")
    
    # 1. Save original image
    cv2.imwrite(str(debug_dir / "00_original.png"), image)
    
    # 2. Save mask (if available)
    if mask is not None:
        cv2.imwrite(str(debug_dir / "01_mask.png"), mask)
    
    # 3. Save visualization with corners
    vis = image.copy()
    
    # Draw corners
    for key, pt in corners.items():
        # Color: red for left, green for right
        color = (0, 0, 255) if key in ['TL', 'BL'] else (0, 255, 0)
        
        # Draw circle
        cv2.circle(vis, (int(pt[0]), int(pt[1])), 12, color, -1, cv2.LINE_AA)
        cv2.circle(vis, (int(pt[0]), int(pt[1])), 14, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Draw label
        cv2.putText(vis, key, 
                   (int(pt[0]) + 20, int(pt[1]) - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3, cv2.LINE_AA)
    
    # Draw quadrilateral
    quad_pts = np.array([
        corners['TL'], corners['TR'], 
        corners['BR'], corners['BL']
    ], dtype=np.int32)
    cv2.polylines(vis, [quad_pts], True, (255, 0, 255), 4, cv2.LINE_AA)
    
    cv2.imwrite(str(debug_dir / "02_corners_visualization.png"), vis)
    
    # 4. Save corner coordinates (JSON)
    corners_data = {
        k: v.tolist() if isinstance(v, np.ndarray) else list(v)
        for k, v in corners.items()
    }
    
    with open(debug_dir / "corners.json", 'w') as f:
        json.dump(corners_data, f, indent=2)
    
    # Also save as text for easy viewing
    with open(debug_dir / "corners.txt", 'w') as f:
        f.write("Court Corner Points\n")
        f.write("=" * 40 + "\n\n")
        for key in ['TL', 'TR', 'BR', 'BL']:
            pt = corners[key]
            f.write(f"{key}: ({pt[0]:.2f}, {pt[1]:.2f})\n")
    
    # 5. Save metadata (JSON)
    with open(debug_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.debug(f"Debug output saved successfully")
    return debug_dir


def detect_from_file(image_path: str, 
                     debug: bool = False,
                     **kwargs) -> Dict[str, Any]:
    """
    Convenience function to detect court from image file.
    
    This is a wrapper around detect_court_api that loads the image from file.
    Useful for quick testing.
    
    Args:
        image_path: Path to image file
        debug: Enable debug mode
        **kwargs: Additional arguments for detect_court_api
        
    Returns:
        Detection result dictionary
        
    Example:
        >>> result = detect_from_file('court.png', debug=True)
        >>> if result['success']:
        >>>     print(result['corners'])
    """
    logger.info(f"Loading image from file: {image_path}")
    
    image = cv2.imread(image_path)
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
        return {
            'success': False,
            'error': f'Failed to load image: {image_path}',
            'error_type': 'ImageLoadError'
        }
    
    return detect_court_api(image, debug=debug, **kwargs)


def detect_from_bytes(image_bytes: bytes,
                      debug: bool = False,
                      **kwargs) -> Dict[str, Any]:
    """
    Detect court from image bytes (e.g., from HTTP request).
    
    Args:
        image_bytes: Image data as bytes
        debug: Enable debug mode
        **kwargs: Additional arguments for detect_court_api
        
    Returns:
        Detection result dictionary
        
    Example:
        >>> with open('court.png', 'rb') as f:
        >>>     image_bytes = f.read()
        >>> result = detect_from_bytes(image_bytes)
    """
    try:
        # Decode image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {
                'success': False,
                'error': 'Failed to decode image from bytes',
                'error_type': 'ImageDecodeError'
            }
        
        return detect_court_api(image, debug=debug, **kwargs)
        
    except Exception as e:
        logger.error(f"Failed to process image bytes: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python api.py <image_path> [--debug]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    debug_mode = '--debug' in sys.argv
    
    print(f"\nTesting API with: {image_path}")
    print(f"Debug mode: {debug_mode}\n")
    
    result = detect_from_file(image_path, debug=debug_mode)
    
    print(json.dumps(result, indent=2))
