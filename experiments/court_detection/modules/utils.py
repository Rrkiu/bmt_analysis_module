"""Common utility functions for court detection

This module provides shared utility functions used across the court detection pipeline:
- I/O operations (save/load images, create directories)
- Image conversions and preprocessing
- Visualization helpers (drawing lines, points, overlays)

Extracted from legacy/pl_1_ransac_cld_bup_ll_v7.py
"""

import cv2
import numpy as np
from pathlib import Path
import datetime
import uuid


def make_output_dir(root_dir: str) -> Path:
    """
    Create timestamped output directory with unique ID.
    
    From legacy lines 51-58
    
    Args:
        root_dir: Root directory path
        
    Returns:
        Path object for created directory
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    run_id = f"{timestamp}_{unique_id}"
    out_dir = Path(root_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def save_image(out_dir: Path, name: str, img: np.ndarray):
    """
    Save image to output directory.
    
    From legacy lines 61-65
    
    Args:
        out_dir: Output directory path
        name: Image name (without extension)
        img: Image array to save
    """
    path = out_dir / f"{name}.png"
    cv2.imwrite(str(path), img)
    print(f"[SAVED] {path}")


def to_bgr(img: np.ndarray) -> np.ndarray:
    """
    Convert grayscale image to BGR if needed.
    
    From legacy lines 68-72
    
    Args:
        img: Input image (grayscale or BGR)
        
    Returns:
        BGR image
    """
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def normalize_mask_to_255(mask_in: np.ndarray) -> np.ndarray:
    """
    Normalize input mask to binary 0/255 using Otsu threshold.
    Handles both grayscale and color inputs.
    
    From legacy lines 79-100
    
    Args:
        mask_in: Input mask (grayscale or color)
        
    Returns:
        Binary mask (0/255)
    """
    if mask_in.ndim == 3:
        mask = cv2.cvtColor(mask_in, cv2.COLOR_BGR2GRAY)
    else:
        mask = mask_in.copy()

    _, binary = cv2.threshold(mask, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Fallback for extreme Otsu results
    fg_ratio = (binary > 0).mean()
    if fg_ratio < 0.0005:
        # Too little foreground, use simple threshold
        _, binary = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
    elif fg_ratio > 0.95:
        # Too much foreground, use lower threshold
        _, binary = cv2.threshold(mask, 50, 255, cv2.THRESH_BINARY)

    return binary


def overlay_points(shape, points: np.ndarray, color=255):
    """
    Create visualization of points on black background.
    
    From legacy lines 1832-1839
    
    Args:
        shape: Output image shape (H, W) or (H, W, C)
        points: Nx2 array of (x, y) coordinates
        color: Color value (grayscale or BGR tuple)
        
    Returns:
        Visualization image
    """
    vis = np.zeros(shape, dtype=np.uint8)
    pts_int = points.astype(np.int32)
    for pt in pts_int:
        if 0 <= pt[1] < shape[0] and 0 <= pt[0] < shape[1]:
            vis[pt[1], pt[0]] = color
    return vis


def draw_line_on_image(img: np.ndarray, p0: np.ndarray, d: np.ndarray, 
                       color, thickness=2):
    """
    Draw infinite line on image.
    
    From legacy lines 1842-1849
    
    Args:
        img: Image to draw on (modified in-place)
        p0: Point on line (x, y)
        d: Direction vector (normalized)
        color: Line color (BGR tuple)
        thickness: Line thickness
    """
    H, W = img.shape[:2]
    # Extend line to image boundaries
    t_max = max(W, H) * 2
    pt1 = (p0 - t_max * d).astype(np.int32)
    pt2 = (p0 + t_max * d).astype(np.int32)
    cv2.line(img, tuple(pt1), tuple(pt2), color, thickness, cv2.LINE_AA)


def draw_point(img: np.ndarray, pt: np.ndarray, color, radius=8, thickness=3):
    """
    Draw point marker on image.
    
    From legacy lines 1852-1855
    
    Args:
        img: Image to draw on (modified in-place)
        pt: Point coordinates (x, y)
        color: Point color (BGR tuple)
        radius: Circle radius
        thickness: Circle thickness (-1 for filled)
    """
    pt_int = tuple(pt.astype(np.int32))
    cv2.circle(img, pt_int, radius, color, thickness, cv2.LINE_AA)

