#!/usr/bin/env python3
"""
Badminton Court 4-Point Estimator (Side-lines only) - Two-Stage Robust Pipeline

Goal:
- Input: Binary-ish mask image where court lines are white on black
- Output: TL/TR/BR/BL (top-left, top-right, bottom-right, bottom-left) endpoints in pixel coords
- Objective: Robustly estimate ONLY the two outer side lines of a badminton court

Pipeline:
  1) Normalize mask to 0/255 binary
  2) Build side-line-only mask with horizontal component removal
  3) Extract points from side-line mask for RANSAC
  4) Fit exactly two near-vertical lines (left/right side lines) via Split-Region RANSAC
  5) **NEW: Two-Stage Refinement**
     - Stage 1: Y-band X-extremity filtering (coarse sideline extraction)
     - Stage 2: RANSAC on filtered points (noise removal & line fitting)
  6) Compute endpoints using y-quantiles with paired-top constraint
  7) Save all intermediate outputs and final coordinates

Key Improvement:
  - Addresses advertisement board noise by extracting only the extreme-x points
    in each y-band (sidelines are by definition the outermost vertical lines)
  - Two-stage approach ensures robustness against noise while preserving accuracy

Usage:
python pl_1_ransac_twostage.py \
  --mask_input path/to/mask.png \
  --out_root results_dir

Optional original frame for overlay:
python pl_1_ransac_twostage.py \
  --mask_input path/to/mask.png \
  --original_input path/to/original.png \
  --out_root results_dir
"""

import argparse
import datetime
import uuid
from pathlib import Path

import cv2
import numpy as np


# ========================================================================
# I/O Utilities
# ========================================================================

def make_output_dir(root_dir: str) -> Path:
    """Create timestamped output directory with unique ID."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    run_id = f"{timestamp}_{unique_id}"
    out_dir = Path(root_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def save_image(out_dir: Path, name: str, img: np.ndarray):
    """Save image to output directory."""
    path = out_dir / f"{name}.png"
    cv2.imwrite(str(path), img)
    print(f"[SAVED] {path}")


def to_bgr(img: np.ndarray) -> np.ndarray:
    """Convert grayscale to BGR if needed."""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


# ========================================================================
# A) Mask Normalization
# ========================================================================

def normalize_mask_to_255(mask_in: np.ndarray) -> np.ndarray:
    """
    Normalize input mask to binary 0/255 using Otsu threshold.
    Handles both grayscale and color inputs.
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


# ========================================================================
# B) Build Side-Line-Only Mask
# ========================================================================

def build_sideline_support_mask(mask255: np.ndarray, out_dir: Path, prefix: str,
                                 open_ks: int, dil_ks: int):
    """
    Apply optional morphological opening and dilation to clean up mask.
    Returns cleaned mask for further processing.
    """
    m = mask255.copy()

    # Optional opening to remove noise
    if open_ks > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_ks, open_ks))
        m_open = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=1)
        save_image(out_dir, f"{prefix}_mask_after_open", m_open)
    else:
        m_open = m

    # Optional dilation to strengthen line support
    if dil_ks > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dil_ks, dil_ks))
        m_dil = cv2.dilate(m_open, k, iterations=1)
        save_image(out_dir, f"{prefix}_mask_after_dilate", m_dil)
    else:
        m_dil = m_open

    return m_dil


def remove_horizontal_components(mask255: np.ndarray, out_dir: Path, name_prefix: str,
                                  horiz_kernel_ratio: float, horiz_iter: int,
                                  central_band_only: bool, band_y0_ratio: float, 
                                  band_y1_ratio: float):
    """
    Remove horizontal line components (net, service lines) using morphological opening.
    
    Args:
        mask255: Binary mask (0/255)
        horiz_kernel_ratio: Horizontal kernel length as ratio of image width (e.g., 0.25)
        horiz_iter: Number of morphological opening iterations
        central_band_only: If True, only remove horizontals in central y-band (net-focused)
        band_y0_ratio: Top of central band as ratio of image height
        band_y1_ratio: Bottom of central band as ratio of image height
    
    Returns:
        mask_no_horiz: Mask with horizontal components removed
        horiz_extracted: Extracted horizontal components (for debugging)
    """
    H, W = mask255.shape[:2]
    mask = mask255.copy()

    # Optionally focus on central band (where net is)
    if central_band_only:
        y0 = int(round(H * band_y0_ratio))
        y1 = int(round(H * band_y1_ratio))
        y0 = max(0, min(H - 1, y0))
        y1 = max(0, min(H, y1))
        if y1 <= y0:
            # Safety fallback
            y0, y1 = int(H * 0.4), int(H * 0.7)

        # Create band mask
        band = np.zeros_like(mask)
        band[y0:y1, :] = 255
        mask_band = cv2.bitwise_and(mask, band)
        
        save_image(out_dir, f"{name_prefix}_central_band_mask", band)
        save_image(out_dir, f"{name_prefix}_mask_in_band", mask_band)
    else:
        mask_band = mask

    # Create horizontal structuring element
    klen = int(max(15, round(W * horiz_kernel_ratio)))
    k_horiz = cv2.getStructuringElement(cv2.MORPH_RECT, (klen, 1))

    # Extract horizontal components via morphological opening
    # Opening = erosion then dilation, keeps only horizontally-connected components
    horiz_extracted = cv2.morphologyEx(mask_band, cv2.MORPH_OPEN, k_horiz, iterations=horiz_iter)
    save_image(out_dir, f"{name_prefix}_horizontal_extracted", horiz_extracted)

    # Remove extracted horizontals from original mask
    mask_no_horiz = cv2.subtract(mask, horiz_extracted)
    save_image(out_dir, f"{name_prefix}_mask_no_horizontal", mask_no_horiz)

    return mask_no_horiz, horiz_extracted


# ========================================================================
# C) Create RANSAC Point Set
# ========================================================================

def extract_edge_points(mask255: np.ndarray, out_dir: Path, prefix: str):
    """
    Extract edge points using morphological gradient.
    Useful when mask is thick and we want precise line boundaries.
    """
    kgrad = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edge = cv2.morphologyEx(mask255, cv2.MORPH_GRADIENT, kgrad)
    save_image(out_dir, f"{prefix}_edge_morph_gradient", edge)
    return edge


def get_ransac_points(mask255: np.ndarray, use_edge: bool, max_points: int,
                      out_dir: Path, prefix: str):
    """
    Extract point set for RANSAC fitting.
    
    Args:
        mask255: Binary mask with side-lines only
        use_edge: If True, use morphological gradient edges; else use mask pixels
        max_points: Maximum number of points to sample (for speed)
    
    Returns:
        points: Nx2 array of (x, y) coordinates
    """
    if use_edge:
        source = extract_edge_points(mask255, out_dir, prefix)
    else:
        source = mask255

    # Extract nonzero pixel coordinates
    ys, xs = np.nonzero(source)
    if len(xs) == 0:
        raise RuntimeError("No points found in mask. Check mask quality and preprocessing parameters.")
    
    points = np.column_stack([xs, ys]).astype(np.float32)

    # Downsample if too many points
    if len(points) > max_points:
        indices = np.random.choice(len(points), max_points, replace=False)
        points = points[indices]

    # Save point preview
    vis = np.zeros(mask255.shape, dtype=np.uint8)
    pts_int = points.astype(np.int32)
    vis[pts_int[:, 1], pts_int[:, 0]] = 255
    save_image(out_dir, f"{prefix}_ransac_point_preview", vis)

    print(f"[INFO] RANSAC point set: {len(points)} points")
    return points


# ========================================================================
# D) Line Model & RANSAC Fitting
# ========================================================================

def line_from_two_points(p1: np.ndarray, p2: np.ndarray):
    """
    Create line model from two points.
    Returns: (p0, direction_vector, normal_vector) or None if points are too close.
    """
    v = p2 - p1
    norm = float(np.linalg.norm(v))
    if norm < 1e-6:
        return None
    
    d = (v / norm).astype(np.float32)  # Direction vector (unit)
    n = np.array([-d[1], d[0]], dtype=np.float32)  # Normal vector (perpendicular)
    p0 = p1.astype(np.float32)  # Point on line
    
    return p0, d, n


def point_line_dist(points: np.ndarray, p0: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Compute perpendicular distance from points to line."""
    return np.abs((points - p0) @ n)


def angle_deg_from_dir(d: np.ndarray) -> float:
    """Convert direction vector to angle in degrees [0, 180)."""
    ang = np.degrees(np.arctan2(float(d[1]), float(d[0])))
    if ang < 0:
        ang += 180.0
    return ang


def is_near_vertical(d: np.ndarray, max_dev_deg: float) -> bool:
    """Check if line is near-vertical: |angle - 90| <= max_dev_deg."""
    ang = angle_deg_from_dir(d)
    return abs(ang - 90.0) <= max_dev_deg


def is_near_horizontal(d: np.ndarray, max_dev_deg: float) -> bool:
    """Check if line is near-horizontal: close to 0° or 180°."""
    ang = angle_deg_from_dir(d)
    return min(abs(ang), abs(ang - 180.0)) <= max_dev_deg


def fit_line_from_points(points: np.ndarray):
    """
    Fit a line to points using cv2.fitLine.
    
    Returns:
        (p0, d, n) - point on line, direction vector, normal vector
        or None if fitting fails
    """
    if len(points) < 2:
        return None
    
    # fitLine returns [vx, vy, x0, y0]
    line_params = cv2.fitLine(points.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy = float(line_params[0]), float(line_params[1])
    x0, y0 = float(line_params[2]), float(line_params[3])
    
    # Normalize direction
    norm = np.sqrt(vx*vx + vy*vy)
    if norm < 1e-6:
        return None
    
    d = np.array([vx/norm, vy/norm], dtype=np.float32)
    n = np.array([-d[1], d[0]], dtype=np.float32)
    p0 = np.array([x0, y0], dtype=np.float32)
    
    return p0, d, n


def ransac_single_line(points: np.ndarray, dist_th: float, max_iter: int, min_inliers: int,
                       forbid_horizontal_deg: float, prefer_vertical_deg: float,
                       enforce_vertical: bool, img_height: int = None,
                       length_weight: float = 0.7):
    """
    Fit a single line using RANSAC with length-based weighting.
    
    Args:
        points: Nx2 array of (x, y) coordinates
        dist_th: Inlier distance threshold in pixels
        max_iter: Maximum RANSAC iterations
        min_inliers: Minimum number of inliers to accept a line
        forbid_horizontal_deg: Reject lines within this angle of horizontal
        prefer_vertical_deg: Acceptable deviation from vertical (90°)
        enforce_vertical: If True, only accept near-vertical lines
        img_height: Image height for length scoring (if None, length scoring disabled)
        length_weight: Weight for length score (0.0-1.0). Higher = prefer longer lines.
    
    Returns:
        (p0, direction, normal, inlier_mask) or None if failed
    """
    n_pts = points.shape[0]
    if n_pts < max(20, min_inliers):
        return None

    best_inliers = None
    best_score = 0
    best_model = None

    for _ in range(max_iter):
        # Sample two random points
        idx = np.random.choice(n_pts, 2, replace=False)
        p1, p2 = points[idx[0]], points[idx[1]]

        # Create line model
        model = line_from_two_points(p1, p2)
        if model is None:
            continue
        
        p0, d, n = model

        # Check orientation constraints
        if forbid_horizontal_deg > 0 and is_near_horizontal(d, forbid_horizontal_deg):
            continue
        
        if enforce_vertical and prefer_vertical_deg < 90 and not is_near_vertical(d, prefer_vertical_deg):
            continue

        # Count inliers
        dists = point_line_dist(points, p0, n)
        inliers = dists < dist_th
        count = np.sum(inliers)
        
        if count < min_inliers:
            continue

        # Compute score with length-based weighting
        if img_height is not None and img_height > 0:
            inlier_y = points[inliers, 1]
            y_span = float(np.max(inlier_y) - np.min(inlier_y))
            length_score = min(y_span / img_height, 1.0)
            score = count * ((1.0 - length_weight) + length_weight * length_score)
        else:
            score = count

        # Update best model
        if score > best_score:
            best_score = score
            best_inliers = inliers
            best_model = model

    # Check if we found a good line
    if best_model is None or best_inliers is None:
        return None
    
    best_count = np.sum(best_inliers)
    if best_count < min_inliers:
        return None

    # Refine using cv2.fitLine on inliers
    p0, d, n = best_model
    inlier_pts = points[best_inliers]
    
    refined = fit_line_from_points(inlier_pts)
    if refined is not None:
        p0_refined, d_refined, n_refined = refined
    else:
        p0_refined, d_refined, n_refined = p0, d, n

    # Recompute inliers with refined model
    dists_refined = point_line_dist(points, p0_refined, n_refined)
    inliers_refined = dists_refined < dist_th

    return p0_refined, d_refined, n_refined, inliers_refined


def ransac_two_lines_split_region(points: np.ndarray, W: int, H: int,
                                   dist_th: float, max_iter: int, min_inliers: int,
                                   forbid_horizontal_deg: float, prefer_vertical_deg: float,
                                   enforce_vertical: bool, split_ratio: float = 0.5,
                                   length_weight: float = 0.7):
    """
    Fit two lines by splitting points into left and right regions.
    This avoids detecting center line by forcing RANSAC to work in separate regions.
    
    Args:
        points: Nx2 array of (x, y) coordinates
        W: Image width
        H: Image height
        split_ratio: X-coordinate ratio to split left/right regions (default 0.5 = middle)
        length_weight: Weight for length-based scoring (0.0-1.0, higher = prefer longer lines)
        ... (other RANSAC parameters)
    
    Returns:
        ((p0_left, d_left, n_left, inliers_left), (p0_right, d_right, n_right, inliers_right))
        or None if failed
    """
    split_x = W * split_ratio
    
    # Split points into left and right regions
    left_mask = points[:, 0] < split_x
    right_mask = points[:, 0] >= split_x
    
    left_points = points[left_mask]
    right_points = points[right_mask]
    
    print(f"[INFO] Split at x={split_x:.1f}: Left={len(left_points)} pts, Right={len(right_points)} pts")
    
    if len(left_points) < min_inliers:
        raise RuntimeError(f"Left region has only {len(left_points)} points, need at least {min_inliers}. "
                          "Try reducing --min_inliers or check mask quality.")
    
    if len(right_points) < min_inliers:
        raise RuntimeError(f"Right region has only {len(right_points)} points, need at least {min_inliers}. "
                          "Try reducing --min_inliers or check mask quality.")
    
    # Fit line in left region
    print("[INFO] Fitting line in LEFT region...")
    left_fit = ransac_single_line(
        left_points, dist_th, max_iter, min_inliers,
        forbid_horizontal_deg, prefer_vertical_deg, enforce_vertical,
        img_height=H, length_weight=length_weight
    )
    
    if left_fit is None:
        raise RuntimeError("RANSAC failed in left region. Try relaxing constraints or check left side mask quality.")
    
    p0_left, d_left, n_left, inliers_left_local = left_fit
    print(f"  Left line: {np.sum(inliers_left_local)} inliers")
    
    # Fit line in right region
    print("[INFO] Fitting line in RIGHT region...")
    right_fit = ransac_single_line(
        right_points, dist_th, max_iter, min_inliers,
        forbid_horizontal_deg, prefer_vertical_deg, enforce_vertical,
        img_height=H, length_weight=length_weight
    )
    
    if right_fit is None:
        raise RuntimeError("RANSAC failed in right region. Try relaxing constraints or check right side mask quality.")
    
    p0_right, d_right, n_right, inliers_right_local = right_fit
    print(f"  Right line: {np.sum(inliers_right_local)} inliers")
    
    # Convert local inlier masks to global indexing
    inliers_left_global = np.zeros(len(points), dtype=bool)
    inliers_left_global[np.where(left_mask)[0][inliers_left_local]] = True
    
    inliers_right_global = np.zeros(len(points), dtype=bool)
    inliers_right_global[np.where(right_mask)[0][inliers_right_local]] = True
    
    return (p0_left, d_left, n_left, inliers_left_global), \
           (p0_right, d_right, n_right, inliers_right_global)


# ========================================================================
# E-0) Bottom-Up Sideline Extraction (Key Innovation!)
# ========================================================================

def extract_seed_points_from_bottom(points: np.ndarray, H: int, 
                                     region_type: str,
                                     bottom_ratio: float = 0.25,
                                     y_bin_size: int = 10,
                                     tolerance_px: float = 10.0):
    """
    Extract seed points from the BOTTOM region of the image.
    
    In the bottom region (court floor), sidelines are reliably the 
    extreme x positions because there's minimal noise from advertisements.
    
    Args:
        points: Nx2 array of points in the region (left or right half)
        H: Image height
        region_type: 'left' or 'right'
        bottom_ratio: Use bottom X% of image for seed extraction (default 25%)
        y_bin_size: Height of y-bands
        tolerance_px: Include points within this distance from extreme x
    
    Returns:
        seed_pts: Points near extreme x in the bottom region
    """
    # Define bottom region
    y_threshold = H * (1 - bottom_ratio)  # e.g., y > 0.75 * H
    
    # Filter to bottom region
    bottom_mask = points[:, 1] >= y_threshold
    bottom_pts = points[bottom_mask]
    
    if len(bottom_pts) < 5:
        return np.array([]).reshape(0, 2)
    
    # Extract extreme x points in each y-band within bottom region
    y_min, y_max = bottom_pts[:, 1].min(), bottom_pts[:, 1].max()
    seed_list = []
    
    for y_start in np.arange(y_min, y_max, y_bin_size):
        y_end = y_start + y_bin_size
        
        band_mask = (bottom_pts[:, 1] >= y_start) & (bottom_pts[:, 1] < y_end)
        band_pts = bottom_pts[band_mask]
        
        if len(band_pts) < 1:
            continue
        
        # Find extreme x based on region type
        if region_type == 'left':
            extreme_x = band_pts[:, 0].min()
            keep_mask = (band_pts[:, 0] - extreme_x) <= tolerance_px
        else:  # 'right'
            extreme_x = band_pts[:, 0].max()
            keep_mask = (extreme_x - band_pts[:, 0]) <= tolerance_px
        
        seed_list.append(band_pts[keep_mask])
    
    if not seed_list:
        return np.array([]).reshape(0, 2)
    
    return np.vstack(seed_list)


def fit_seed_line(seed_pts: np.ndarray, dist_th: float = 5.0):
    """
    Fit a line to seed points using RANSAC.
    Returns (p0, d, n) or None.
    """
    if len(seed_pts) < 5:
        return fit_line_from_points(seed_pts)
    
    n_pts = len(seed_pts)
    best_inliers = None
    best_count = 0
    best_model = None
    
    for _ in range(500):
        idx = np.random.choice(n_pts, 2, replace=False)
        model = line_from_two_points(seed_pts[idx[0]], seed_pts[idx[1]])
        if model is None:
            continue
        
        p0, d, n = model
        dists = point_line_dist(seed_pts, p0, n)
        inliers = dists < dist_th
        count = np.sum(inliers)
        
        if count > best_count:
            best_count = count
            best_inliers = inliers
            best_model = model
    
    if best_model is None:
        return fit_line_from_points(seed_pts)
    
    # Refine with inliers
    inlier_pts = seed_pts[best_inliers]
    return fit_line_from_points(inlier_pts)


def compute_local_linearity_score(points: np.ndarray, k_neighbors: int = 10):
    """
    Compute local linearity score for each point.
    
    Points on a true line will have neighbors that are collinear (low residual).
    Points in noise clusters will have neighbors that are scattered (high residual).
    
    Args:
        points: Nx2 array of (x, y) coordinates
        k_neighbors: Number of nearest neighbors to consider
    
    Returns:
        scores: N array of linearity scores (lower = more linear = likely true line)
    """
    from scipy.spatial import cKDTree
    
    n_pts = len(points)
    if n_pts < k_neighbors + 1:
        return np.zeros(n_pts)
    
    # Build KD-tree for efficient neighbor search
    tree = cKDTree(points)
    
    scores = np.zeros(n_pts)
    
    for i in range(n_pts):
        # Find k nearest neighbors (including self)
        distances, indices = tree.query(points[i], k=min(k_neighbors + 1, n_pts))
        
        neighbor_pts = points[indices]
        
        if len(neighbor_pts) < 3:
            scores[i] = float('inf')
            continue
        
        # Fit line to neighbors
        line_params = cv2.fitLine(neighbor_pts.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01)
        vx, vy = float(line_params[0]), float(line_params[1])
        x0, y0 = float(line_params[2]), float(line_params[3])
        
        # Compute perpendicular distances (residuals)
        p0 = np.array([x0, y0])
        d = np.array([vx, vy])
        n = np.array([-vy, vx])  # Normal vector
        
        residuals = np.abs((neighbor_pts - p0) @ n)
        
        # Score = mean residual (lower = more linear)
        scores[i] = np.mean(residuals)
    
    return scores


def filter_by_local_linearity(points: np.ndarray, 
                               k_neighbors: int = 10,
                               max_residual: float = 5.0,
                               min_neighbors: int = 5):
    """
    Filter points based on local linearity.
    
    True sideline points have collinear neighbors (low residual).
    Noise cluster points have scattered neighbors (high residual).
    
    Args:
        points: Nx2 array of points
        k_neighbors: Number of neighbors for linearity check
        max_residual: Maximum allowed mean residual to be considered "linear"
        min_neighbors: Minimum neighbors required
    
    Returns:
        filtered_points: Points that pass linearity test
        mask: Boolean mask of kept points
    """
    if len(points) < min_neighbors:
        return points, np.ones(len(points), dtype=bool)
    
    scores = compute_local_linearity_score(points, k_neighbors)
    
    # Keep points with low residual (high linearity)
    mask = scores <= max_residual
    
    return points[mask], mask


def filter_by_continuity_density(points: np.ndarray,
                                  y_bin_size: int = 20,
                                  min_density: int = 3,
                                  gap_threshold: int = 2):
    """
    Filter points based on vertical continuity and density.
    
    True sidelines have consistent point density across y-bands.
    Noise clusters have gaps or isolated dense regions.
    
    Args:
        points: Nx2 array of points
        y_bin_size: Height of y-bands
        min_density: Minimum points per band to be considered valid
        gap_threshold: Max consecutive empty bands allowed
    
    Returns:
        filtered_points: Points in continuous regions
    """
    if len(points) < 10:
        return points
    
    y_min, y_max = points[:, 1].min(), points[:, 1].max()
    
    # Count points in each y-band
    n_bands = int(np.ceil((y_max - y_min) / y_bin_size))
    band_counts = np.zeros(n_bands, dtype=int)
    band_points = [[] for _ in range(n_bands)]
    
    for i, pt in enumerate(points):
        band_idx = int((pt[1] - y_min) / y_bin_size)
        band_idx = min(band_idx, n_bands - 1)
        band_counts[band_idx] += 1
        band_points[band_idx].append(i)
    
    # Find the longest continuous region with sufficient density
    valid_bands = band_counts >= min_density
    
    # Find continuous segments
    segments = []
    start = None
    gap_count = 0
    
    for i in range(n_bands):
        if valid_bands[i]:
            if start is None:
                start = i
            gap_count = 0
        else:
            gap_count += 1
            if gap_count > gap_threshold and start is not None:
                segments.append((start, i - gap_count))
                start = None
    
    if start is not None:
        segments.append((start, n_bands - 1))
    
    if not segments:
        return points
    
    # Use the longest segment
    longest = max(segments, key=lambda s: s[1] - s[0])
    
    # Collect points from valid bands in longest segment
    valid_indices = []
    for band_idx in range(longest[0], longest[1] + 1):
        if band_counts[band_idx] >= 1:  # Include bands with at least 1 point
            valid_indices.extend(band_points[band_idx])
    
    if not valid_indices:
        return points
    
    return points[np.array(valid_indices)]


def advanced_noise_filter(points: np.ndarray, seed_line,
                          k_neighbors: int = 12,
                          linearity_threshold: float = 4.0,
                          density_bin_size: int = 20,
                          min_density: int = 2):
    """
    Advanced noise filtering combining multiple techniques:
    
    1. Local Linearity: Remove points whose neighbors aren't collinear
    2. Seed Line Distance: Remove points too far from expected line
    3. Continuity Density: Remove isolated clusters
    
    Args:
        points: Input points
        seed_line: (p0, d, n) reference line from bottom region
        k_neighbors: Neighbors for linearity check
        linearity_threshold: Max residual for linearity
        density_bin_size: Y-band size for density check
        min_density: Min points per band
    
    Returns:
        filtered_points: Clean points along sideline
    """
    if len(points) < 10:
        return points
    
    print(f"      [Advanced Filter] Input: {len(points)} points")
    
    # Step 1: Local Linearity Filter
    try:
        linear_pts, linear_mask = filter_by_local_linearity(
            points, 
            k_neighbors=k_neighbors,
            max_residual=linearity_threshold
        )
        print(f"      [Advanced Filter] After linearity: {len(linear_pts)} points")
    except Exception as e:
        print(f"      [Advanced Filter] Linearity filter failed: {e}, skipping")
        linear_pts = points
    
    if len(linear_pts) < 10:
        print(f"      [Advanced Filter] Too few points after linearity, using original")
        linear_pts = points
    
    # Step 2: Seed Line Distance Filter (if seed_line provided)
    if seed_line is not None:
        p0, d, n = seed_line
        dists = point_line_dist(linear_pts, p0, n)
        
        # Adaptive threshold based on distribution
        dist_median = np.median(dists)
        dist_std = np.std(dists)
        dist_threshold = dist_median + 2 * dist_std
        dist_threshold = max(dist_threshold, 10.0)  # At least 10 pixels
        
        dist_mask = dists <= dist_threshold
        dist_pts = linear_pts[dist_mask]
        print(f"      [Advanced Filter] After distance: {len(dist_pts)} points (th={dist_threshold:.1f})")
        
        if len(dist_pts) >= 10:
            linear_pts = dist_pts
    
    # Step 3: Continuity Density Filter
    try:
        final_pts = filter_by_continuity_density(
            linear_pts,
            y_bin_size=density_bin_size,
            min_density=min_density,
            gap_threshold=3
        )
        print(f"      [Advanced Filter] After continuity: {len(final_pts)} points")
    except Exception as e:
        print(f"      [Advanced Filter] Continuity filter failed: {e}, skipping")
        final_pts = linear_pts
    
    if len(final_pts) < 10:
        print(f"      [Advanced Filter] Too few points after continuity, using previous")
        final_pts = linear_pts
    
    return final_pts


def extend_line_to_full_image(points: np.ndarray, seed_line, 
                               region_type: str,
                               H: int,
                               dist_th: float = 5.0,
                               x_tolerance: float = 20.0,
                               continuity_th: float = 30.0,
                               y_bin_size: int = 15,
                               k_neighbors: int = 12,
                               linearity_th: float = 4.0):
    """
    Extend the seed line to the full image by collecting consistent points.
    
    **IMPROVED STRATEGY (Method 3 + Local Linearity Filter)**
    
    1. Use seed line to predict expected x at each y-level
    2. Select points near the expected x (not just extreme x)
    3. Check continuity: reject bands where x jumps too much from previous
    4. **NEW: Local linearity filter** - remove noise clusters where neighbors aren't collinear
    
    This approach is robust because:
    - Seed line provides strong geometric prior
    - Continuity check filters out isolated noise clusters
    - Local linearity distinguishes true line points from scattered noise
    
    Args:
        points: All points in the region (left or right half)
        seed_line: (p0, d, n) from bottom region
        region_type: 'left' or 'right'
        H: Image height
        dist_th: Max perpendicular distance from seed line (initial filter)
        x_tolerance: Tolerance around expected x position
        continuity_th: Max allowed x-jump between adjacent y-bands
        y_bin_size: Height of y-bands for processing
        k_neighbors: Number of neighbors for local linearity check
        linearity_th: Max residual threshold for linearity filter
    
    Returns:
        extended_pts: Points along the sideline
    """
    if seed_line is None:
        return np.array([]).reshape(0, 2)
    
    p0, d, n = seed_line
    
    # Helper: compute x at given y using seed line
    def expected_x_at_y(y):
        if abs(d[1]) < 1e-9:
            return p0[0]  # Horizontal line edge case
        t = (y - p0[1]) / d[1]
        return p0[0] + t * d[0]
    
    # First filter: points reasonably close to seed line (loose filter)
    dists = point_line_dist(points, p0, n)
    loose_dist_th = dist_th * 3  # Use larger threshold for initial filtering
    near_line_mask = dists < loose_dist_th
    near_line_pts = points[near_line_mask]
    
    if len(near_line_pts) < 10:
        return near_line_pts
    
    # Process y-bands from bottom to top
    y_min, y_max = near_line_pts[:, 1].min(), near_line_pts[:, 1].max()
    
    # Sort bands from bottom (high y) to top (low y) for continuity tracking
    y_bands = list(np.arange(y_max, y_min, -y_bin_size))
    
    filtered_list = []
    prev_x = None  # Track previous band's x for continuity
    prev_y = None
    
    for y_start in y_bands:
        y_end = y_start - y_bin_size
        
        # Get points in this y-band
        band_mask = (near_line_pts[:, 1] <= y_start) & (near_line_pts[:, 1] > y_end)
        band_pts = near_line_pts[band_mask]
        
        if len(band_pts) < 1:
            continue
        
        # Calculate expected x from seed line
        band_y_center = (y_start + y_end) / 2
        expected_x = expected_x_at_y(band_y_center)
        
        # Strategy: Find points near expected x
        x_diffs = np.abs(band_pts[:, 0] - expected_x)
        near_expected_mask = x_diffs <= x_tolerance
        
        # Also consider extreme x as backup (in case expected is slightly off)
        if region_type == 'left':
            extreme_x = band_pts[:, 0].min()
            near_extreme_mask = (band_pts[:, 0] - extreme_x) <= x_tolerance
        else:
            extreme_x = band_pts[:, 0].max()
            near_extreme_mask = (extreme_x - band_pts[:, 0]) <= x_tolerance
        
        # Combine: points that are near expected OR near extreme
        combined_mask = near_expected_mask | near_extreme_mask
        candidate_pts = band_pts[combined_mask]
        
        if len(candidate_pts) < 1:
            continue
        
        # Compute the representative x for this band (median of candidates)
        if region_type == 'left':
            band_repr_x = np.percentile(candidate_pts[:, 0], 25)  # Use lower quartile for left
        else:
            band_repr_x = np.percentile(candidate_pts[:, 0], 75)  # Use upper quartile for right
        
        # Continuity check: compare with previous band
        if prev_x is not None:
            x_jump = abs(band_repr_x - prev_x)
            
            # Allow some slack based on y-distance (lines are not perfectly vertical)
            y_dist = abs(band_y_center - prev_y) if prev_y is not None else y_bin_size
            expected_x_change = abs(d[0] / d[1]) * y_dist if abs(d[1]) > 1e-9 else 0
            allowed_jump = continuity_th + expected_x_change
            
            if x_jump > allowed_jump:
                # This band has discontinuity - likely noise
                # Option 1: Skip entirely
                # Option 2: Use expected_x to find better points
                
                # Try to find points closer to expected line
                strict_mask = x_diffs <= (x_tolerance * 0.5)
                strict_pts = band_pts[strict_mask]
                
                if len(strict_pts) >= 1:
                    candidate_pts = strict_pts
                    if region_type == 'left':
                        band_repr_x = np.min(strict_pts[:, 0])
                    else:
                        band_repr_x = np.max(strict_pts[:, 0])
                    
                    # Recheck continuity
                    if abs(band_repr_x - prev_x) > allowed_jump:
                        continue  # Still bad, skip this band
                else:
                    continue  # No good points, skip
        
        # Final filter: keep only points close to band representative x
        final_tolerance = x_tolerance * 0.8
        if region_type == 'left':
            final_mask = (candidate_pts[:, 0] - band_repr_x) <= final_tolerance
        else:
            final_mask = (band_repr_x - candidate_pts[:, 0]) <= final_tolerance
        
        final_pts = candidate_pts[final_mask]
        
        if len(final_pts) >= 1:
            filtered_list.append(final_pts)
            prev_x = band_repr_x
            prev_y = band_y_center
    
    if not filtered_list:
        # Fallback: return points close to seed line
        strict_mask = dists < dist_th
        return points[strict_mask]
    
    extended_pts = np.vstack(filtered_list)
    
    # Apply advanced noise filter for final cleanup
    final_pts = advanced_noise_filter(
        extended_pts, seed_line,
        k_neighbors=k_neighbors,
        linearity_threshold=linearity_th,
        density_bin_size=y_bin_size,
        min_density=2
    )
    
    return final_pts


def bottom_up_sideline_extraction(points: np.ndarray, H: int, region_type: str,
                                   bottom_ratio: float = 0.25,
                                   seed_y_bin: int = 10,
                                   seed_tolerance: float = 10.0,
                                   extend_dist_th: float = 8.0,
                                   extend_x_tolerance: float = 15.0,
                                   continuity_th: float = 30.0,
                                   extend_y_bin: int = 15,
                                   k_neighbors: int = 12,
                                   linearity_th: float = 4.0,
                                   out_dir: Path = None,
                                   debug_prefix: str = ""):
    """
    Bottom-Up Sideline Extraction Algorithm:
    
    1. Extract seed points from bottom region (reliable, minimal noise)
    2. Fit seed line to bottom points
    3. Extend upward using seed line slope + continuity check
    4. **NEW: Apply local linearity filter to remove noise clusters**
    5. Final line fit on extended points
    
    This approach is robust because:
    - Bottom of court has minimal advertisement noise
    - Seed line provides strong geometric prior for filtering
    - Continuity check eliminates isolated noise
    - Local linearity filter removes scattered cluster points
    
    Args:
        points: Points in this region (left or right half of image)
        H: Image height
        region_type: 'left' or 'right'
        bottom_ratio: Use bottom X% for seed extraction
        seed_y_bin: Y-band size for seed extraction
        seed_tolerance: X-tolerance for seed point selection
        extend_dist_th: Distance threshold for extending line
        extend_x_tolerance: X-tolerance when extending
        continuity_th: Max allowed x-jump between adjacent y-bands
        extend_y_bin: Y-band size for extension process
        k_neighbors: Number of neighbors for local linearity check
        linearity_th: Max residual threshold for linearity filter
    
    Returns:
        (p0, d, n, final_pts) - Line parameters and final point set
    """
    print(f"\n  [{region_type.upper()}] Bottom-Up Extraction:")
    print(f"    Input points: {len(points)}")
    
    # Step 1: Extract seed points from bottom
    seed_pts = extract_seed_points_from_bottom(
        points, H, region_type,
        bottom_ratio=bottom_ratio,
        y_bin_size=seed_y_bin,
        tolerance_px=seed_tolerance
    )
    print(f"    Seed points (bottom {bottom_ratio*100:.0f}%): {len(seed_pts)}")
    
    if len(seed_pts) < 5:
        raise RuntimeError(f"Not enough seed points for {region_type} sideline. "
                          f"Found {len(seed_pts)}, need at least 5.")
    
    # Save seed visualization
    if out_dir is not None:
        vis_seed = np.zeros((H, max(int(points[:, 0].max()) + 50, 1920)), dtype=np.uint8)
        for pt in seed_pts.astype(np.int32):
            if 0 <= pt[1] < vis_seed.shape[0] and 0 <= pt[0] < vis_seed.shape[1]:
                vis_seed[pt[1], pt[0]] = 255
        save_image(out_dir, f"{debug_prefix}_01_seed_points", vis_seed)
    
    # Step 2: Fit seed line
    seed_line = fit_seed_line(seed_pts, dist_th=5.0)
    
    if seed_line is None:
        raise RuntimeError(f"Failed to fit seed line for {region_type} sideline.")
    
    print(f"    Seed line fitted")
    
    # Step 3: Extend to full image
    extended_pts = extend_line_to_full_image(
        points, seed_line, region_type,
        H=H,
        dist_th=extend_dist_th,
        x_tolerance=extend_x_tolerance,
        continuity_th=continuity_th,
        y_bin_size=extend_y_bin,
        k_neighbors=k_neighbors,
        linearity_th=linearity_th
    )
    print(f"    Extended points: {len(extended_pts)}")
    
    # Save extended visualization
    if out_dir is not None:
        vis_ext = np.zeros((H, max(int(points[:, 0].max()) + 50, 1920)), dtype=np.uint8)
        for pt in extended_pts.astype(np.int32):
            if 0 <= pt[1] < vis_ext.shape[0] and 0 <= pt[0] < vis_ext.shape[1]:
                vis_ext[pt[1], pt[0]] = 255
        save_image(out_dir, f"{debug_prefix}_02_extended_points", vis_ext)
    
    # Step 4: Final line fit
    final_line = fit_line_from_points(extended_pts)
    
    if final_line is None:
        raise RuntimeError(f"Failed to fit final line for {region_type} sideline.")
    
    p0, d, n = final_line
    print(f"    Final line fitted with {len(extended_pts)} points")
    
    return p0, d, n, extended_pts


# ========================================================================
# E) Two-Stage Sideline Refinement (NEW!)
# ========================================================================

def filter_inliers_by_x_extremity(inlier_pts: np.ndarray, region_type: str,
                                   y_bin_size: int = 15, tolerance_px: float = 8.0,
                                   min_pts_per_bin: int = 3):
    """
    Stage 1: Filter inliers to keep only x-extreme points in each y-band.
    
    For left sideline: keep points with minimum x (leftmost) in each y-band
    For right sideline: keep points with maximum x (rightmost) in each y-band
    
    Args:
        inlier_pts: Nx2 array of (x, y) inlier coordinates
        region_type: 'left' or 'right'
        y_bin_size: Height of each y-band in pixels
        tolerance_px: Include points within this distance from extreme x
        min_pts_per_bin: Minimum points in a bin to consider it valid
    
    Returns:
        filtered_pts: Mx2 array of filtered points (M <= N)
    """
    if len(inlier_pts) < 10:
        return inlier_pts
    
    y_min, y_max = inlier_pts[:, 1].min(), inlier_pts[:, 1].max()
    filtered_list = []
    
    # Process each y-band
    for y_start in np.arange(y_min, y_max, y_bin_size):
        y_end = y_start + y_bin_size
        
        # Get points in this y-band
        band_mask = (inlier_pts[:, 1] >= y_start) & (inlier_pts[:, 1] < y_end)
        band_pts = inlier_pts[band_mask]
        
        if len(band_pts) < min_pts_per_bin:
            continue
        
        # Find extreme x
        if region_type == 'left':
            extreme_x = band_pts[:, 0].min()
        else:  # 'right'
            extreme_x = band_pts[:, 0].max()
        
        # Keep points close to extreme x
        x_mask = np.abs(band_pts[:, 0] - extreme_x) <= tolerance_px
        filtered_list.append(band_pts[x_mask])
    
    if not filtered_list:
        print(f"[WARNING] X-extremity filtering returned no points for {region_type} region")
        return inlier_pts  # Fallback: return original
    
    filtered_pts = np.vstack(filtered_list)
    return filtered_pts


def ransac_on_filtered_points(filtered_pts: np.ndarray, dist_th: float, 
                               max_iter: int = 500, min_inliers: int = 50):
    """
    Stage 2: Run RANSAC on filtered points to remove remaining outliers
    and fit a clean line.
    
    Args:
        filtered_pts: Nx2 array of pre-filtered points
        dist_th: Inlier distance threshold
        max_iter: RANSAC iterations
        min_inliers: Minimum inliers to accept
    
    Returns:
        (p0, d, n, refined_pts) or None if failed
    """
    if len(filtered_pts) < min_inliers:
        # Not enough points, just fit directly
        fit = fit_line_from_points(filtered_pts)
        if fit is None:
            return None
        p0, d, n = fit
        return p0, d, n, filtered_pts
    
    n_pts = len(filtered_pts)
    best_inliers = None
    best_count = 0
    best_model = None
    
    for _ in range(max_iter):
        # Sample two random points
        idx = np.random.choice(n_pts, 2, replace=False)
        p1, p2 = filtered_pts[idx[0]], filtered_pts[idx[1]]
        
        model = line_from_two_points(p1, p2)
        if model is None:
            continue
        
        p0, d, n = model
        
        # Count inliers
        dists = point_line_dist(filtered_pts, p0, n)
        inliers = dists < dist_th
        count = np.sum(inliers)
        
        if count > best_count:
            best_count = count
            best_inliers = inliers
            best_model = model
    
    if best_model is None or best_count < min(min_inliers, len(filtered_pts) // 2):
        # Fallback: fit all points
        fit = fit_line_from_points(filtered_pts)
        if fit is None:
            return None
        p0, d, n = fit
        return p0, d, n, filtered_pts
    
    # Refine with inliers
    inlier_pts = filtered_pts[best_inliers]
    refined = fit_line_from_points(inlier_pts)
    
    if refined is not None:
        p0, d, n = refined
    else:
        p0, d, n = best_model
    
    return p0, d, n, inlier_pts


def two_stage_sideline_refinement(inlier_pts: np.ndarray, region_type: str,
                                   y_bin_size: int, x_tolerance: float,
                                   stage2_dist_th: float, stage2_iter: int,
                                   stage2_min_inliers: int,
                                   out_dir: Path = None, debug_prefix: str = ""):
    """
    Two-stage sideline refinement:
    
    Stage 1: Y-band X-extremity filtering
        - Divide inliers into horizontal bands
        - In each band, keep only points near the extreme x position
        - This removes advertisement noise that's not at the sideline position
    
    Stage 2: RANSAC on filtered points
        - Run RANSAC on the filtered points to remove remaining outliers
        - Fit a clean line to the refined point set
    
    Args:
        inlier_pts: Nx2 array of initial RANSAC inliers
        region_type: 'left' or 'right'
        y_bin_size: Size of y-bands for Stage 1
        x_tolerance: Tolerance for x-extremity in Stage 1
        stage2_dist_th: RANSAC distance threshold for Stage 2
        stage2_iter: RANSAC iterations for Stage 2
        stage2_min_inliers: Minimum inliers for Stage 2
        out_dir: Output directory for debug images
        debug_prefix: Prefix for debug image names
    
    Returns:
        (p0, d, n, refined_pts) - Line parameters and refined point set
    """
    print(f"[STAGE 1] X-extremity filtering for {region_type} region...")
    print(f"  Input: {len(inlier_pts)} points")
    
    # Stage 1: X-extremity filtering
    stage1_pts = filter_inliers_by_x_extremity(
        inlier_pts, region_type,
        y_bin_size=y_bin_size,
        tolerance_px=x_tolerance
    )
    print(f"  After Stage 1: {len(stage1_pts)} points")
    
    # Save Stage 1 visualization
    if out_dir is not None:
        vis_shape = (1080, 1920)  # Default, will be overwritten if needed
        if len(inlier_pts) > 0:
            max_y = int(max(inlier_pts[:, 1].max(), stage1_pts[:, 1].max())) + 50
            max_x = int(max(inlier_pts[:, 0].max(), stage1_pts[:, 0].max())) + 50
            vis_shape = (max_y, max_x)
        
        # Original inliers in gray, Stage 1 points in white
        vis = np.zeros(vis_shape, dtype=np.uint8)
        for pt in inlier_pts.astype(np.int32):
            if 0 <= pt[1] < vis_shape[0] and 0 <= pt[0] < vis_shape[1]:
                vis[pt[1], pt[0]] = 80  # Gray for original
        for pt in stage1_pts.astype(np.int32):
            if 0 <= pt[1] < vis_shape[0] and 0 <= pt[0] < vis_shape[1]:
                vis[pt[1], pt[0]] = 255  # White for filtered
        save_image(out_dir, f"{debug_prefix}_stage1_xextreme", vis)
    
    # Stage 2: RANSAC on filtered points
    print(f"[STAGE 2] RANSAC refinement for {region_type} region...")
    
    result = ransac_on_filtered_points(
        stage1_pts, 
        dist_th=stage2_dist_th,
        max_iter=stage2_iter,
        min_inliers=stage2_min_inliers
    )
    
    if result is None:
        raise RuntimeError(f"Stage 2 RANSAC failed for {region_type} region")
    
    p0, d, n, refined_pts = result
    print(f"  After Stage 2: {len(refined_pts)} points")
    
    # Save Stage 2 visualization
    if out_dir is not None:
        vis2 = np.zeros(vis_shape, dtype=np.uint8)
        for pt in refined_pts.astype(np.int32):
            if 0 <= pt[1] < vis_shape[0] and 0 <= pt[0] < vis_shape[1]:
                vis2[pt[1], pt[0]] = 255
        save_image(out_dir, f"{debug_prefix}_stage2_refined", vis2)
    
    return p0, d, n, refined_pts


# ========================================================================
# F) Endpoint Computation - Line Equation Based (IMPROVED!)
# ========================================================================

def x_at_y(p0: np.ndarray, d: np.ndarray, y: float) -> float:
    """
    Compute x-coordinate where line intersects horizontal line at y.
    Line parametric form: point = p0 + t*d
    Solve: p0[1] + t*d[1] = y  =>  t = (y - p0[1]) / d[1]
    Then: x = p0[0] + t*d[0]
    """
    if abs(d[1]) < 1e-9:
        return None  # Line is horizontal, no unique intersection
    
    t = (y - p0[1]) / d[1]
    x = p0[0] + t * d[0]
    return x


def compute_endpoints_line_equation(p0: np.ndarray, d: np.ndarray,
                                     inlier_pts: np.ndarray,
                                     H: int, W: int,
                                     top_margin: float = 0.02,
                                     bot_margin: float = 0.02,
                                     use_extrapolation: bool = True):
    """
    Compute line endpoints using LINE EQUATION instead of point percentiles.
    
    **KEY IMPROVEMENT**: 
    - Previous method: Use percentile of detected points → misses line ends if points are sparse
    - New method: Extrapolate line equation to image boundaries → captures full line extent
    
    Strategy:
    1. Find the y-range where we have actual detected points (for reference)
    2. Extrapolate the fitted line to extend beyond detected points
    3. Use image boundaries (with margin) as the endpoint y-coordinates
    4. Compute x at those y-coordinates using line equation
    
    Args:
        p0, d: Line parameters (point and direction vector)
        inlier_pts: Detected points (used for sanity check and fallback)
        H, W: Image dimensions
        top_margin: Margin from top of image as ratio (0.02 = 2%)
        bot_margin: Margin from bottom of image as ratio
        use_extrapolation: If True, extrapolate beyond detected points
    
    Returns:
        (top_point, bottom_point, y_top, y_bot)
    """
    if len(inlier_pts) < 5:
        return None, None, None, None
    
    # Get y-range of detected points
    pts_y_min = inlier_pts[:, 1].min()
    pts_y_max = inlier_pts[:, 1].max()
    
    if use_extrapolation:
        # Use image boundaries with margin
        y_top_target = H * top_margin
        y_bot_target = H * (1 - bot_margin)
        
        # But don't extrapolate too far beyond detected points
        # Allow extrapolation up to 20% of detected range
        pts_y_range = pts_y_max - pts_y_min
        max_extrapolation = pts_y_range * 0.3  # 30% extrapolation allowed
        
        y_top = max(pts_y_min - max_extrapolation, y_top_target)
        y_bot = min(pts_y_max + max_extrapolation, y_bot_target)
    else:
        # Use detected point range (original behavior)
        y_top = pts_y_min
        y_bot = pts_y_max
    
    # Compute x-coordinates using line equation
    x_top = x_at_y(p0, d, y_top)
    x_bot = x_at_y(p0, d, y_bot)
    
    if x_top is None or x_bot is None:
        return None, None, None, None
    
    # Sanity check: x should be within image bounds (with some tolerance)
    tolerance = W * 0.1  # 10% tolerance
    if x_top < -tolerance or x_top > W + tolerance:
        # Line goes out of bounds at top, clip to detected range
        y_top = pts_y_min
        x_top = x_at_y(p0, d, y_top)
    
    if x_bot < -tolerance or x_bot > W + tolerance:
        # Line goes out of bounds at bottom, clip to detected range
        y_bot = pts_y_max
        x_bot = x_at_y(p0, d, y_bot)
    
    if x_top is None or x_bot is None:
        return None, None, None, None
    
    top_pt = np.array([x_top, y_top], dtype=np.float32)
    bot_pt = np.array([x_bot, y_bot], dtype=np.float32)
    
    return top_pt, bot_pt, y_top, y_bot


def compute_endpoints_yquant(inlier_pts: np.ndarray, p0: np.ndarray, d: np.ndarray,
                              top_pct: float, bot_pct: float):
    """
    Compute line endpoints using y-percentiles of inlier points.
    (Legacy method - kept for compatibility)
    
    Args:
        inlier_pts: Nx2 array of inlier points
        p0, d: Line parameters (point and direction)
        top_pct: Percentile for top endpoint (smaller = higher)
        bot_pct: Percentile for bottom endpoint (larger = lower)
    
    Returns:
        (top_point, bottom_point, y_top, y_bot)
    """
    if len(inlier_pts) < 10:
        return None, None, None, None

    y_vals = inlier_pts[:, 1]
    
    # Compute y-coordinates using percentiles
    y_top = np.percentile(y_vals, top_pct)
    y_bot = np.percentile(y_vals, bot_pct)

    # Compute x-coordinates by intersecting with horizontal lines
    x_top = x_at_y(p0, d, y_top)
    x_bot = x_at_y(p0, d, y_bot)

    if x_top is None or x_bot is None:
        return None, None, None, None

    top_pt = np.array([x_top, y_top], dtype=np.float32)
    bot_pt = np.array([x_bot, y_bot], dtype=np.float32)

    return top_pt, bot_pt, y_top, y_bot


def enforce_paired_top_constraint_line_equation(L_inliers: np.ndarray, R_inliers: np.ndarray,
                                                  L_p0: np.ndarray, L_d: np.ndarray,
                                                  R_p0: np.ndarray, R_d: np.ndarray,
                                                  H: int, W: int,
                                                  top_margin: float, bot_margin: float,
                                                  max_top_y_diff: float,
                                                  use_extrapolation: bool = True):
    """
    Compute endpoints using line equation with paired-top constraint.
    
    **IMPROVED VERSION**: Uses line extrapolation instead of point percentiles.
    
    The paired-top constraint ensures TL.y ≈ TR.y (top corners at same height).
    
    Strategy:
    1. Compute endpoints for both lines using line equation extrapolation
    2. If top y-coordinates differ too much:
       - Use the LOWER (larger y) of the two as the unified top
       - This ensures we stay within the detected range of BOTH lines
       - Avoids extreme extrapolation errors
    
    Returns:
        TL, TR, BL, BR, method_info, final_top_y_diff, yL_top, yR_top
    """
    # Compute endpoints using line equation
    TL, BL, yL_top, yL_bot = compute_endpoints_line_equation(
        L_p0, L_d, L_inliers, H, W, top_margin, bot_margin, use_extrapolation
    )
    
    TR, BR, yR_top, yR_bot = compute_endpoints_line_equation(
        R_p0, R_d, R_inliers, H, W, top_margin, bot_margin, use_extrapolation
    )
    
    if TL is None or TR is None:
        return None, None, None, None, "failed", None, None, None
    
    # Debug info
    print(f"    Initial endpoints: TL=({TL[0]:.1f}, {TL[1]:.1f}), TR=({TR[0]:.1f}, {TR[1]:.1f})")
    print(f"    Initial endpoints: BL=({BL[0]:.1f}, {BL[1]:.1f}), BR=({BR[0]:.1f}, {BR[1]:.1f})")
    
    # Check paired-top constraint
    top_y_diff = abs(yL_top - yR_top)
    
    if top_y_diff <= max_top_y_diff:
        # Constraint already satisfied
        return TL, TR, BL, BR, "line_equation", top_y_diff, yL_top, yR_top
    
    # IMPORTANT: Use the LOWER top (larger y) to stay within both lines' detected range
    # This is safer than using the higher top which might cause extreme extrapolation
    unified_y_top = max(yL_top, yR_top)  # max y = lower position in image
    
    # But also check: unified_y_top shouldn't be too low (below midpoint)
    # If it is, something is wrong - fall back to original values
    image_midpoint = H * 0.5
    if unified_y_top > image_midpoint:
        print(f"    [WARNING] unified_y_top ({unified_y_top:.1f}) is below image midpoint, using original values")
        return TL, TR, BL, BR, "line_equation_no_unify", top_y_diff, yL_top, yR_top
    
    # Recompute x at unified y_top
    xL_top_new = x_at_y(L_p0, L_d, unified_y_top)
    xR_top_new = x_at_y(R_p0, R_d, unified_y_top)
    
    if xL_top_new is None or xR_top_new is None:
        # Fallback to original
        return TL, TR, BL, BR, "line_equation_fallback", top_y_diff, yL_top, yR_top
    
    # Sanity check: the new x values should still make sense
    # TL.x should be less than TR.x (left is left, right is right)
    if xL_top_new >= xR_top_new:
        print(f"    [WARNING] After unification, TL.x ({xL_top_new:.1f}) >= TR.x ({xR_top_new:.1f}), using original")
        return TL, TR, BL, BR, "line_equation_no_unify", top_y_diff, yL_top, yR_top
    
    # Check that x values are within reasonable bounds
    if xL_top_new < -W * 0.2 or xR_top_new > W * 1.2:
        print(f"    [WARNING] Unified x values out of bounds, using original")
        return TL, TR, BL, BR, "line_equation_no_unify", top_y_diff, yL_top, yR_top
    
    TL_new = np.array([xL_top_new, unified_y_top], dtype=np.float32)
    TR_new = np.array([xR_top_new, unified_y_top], dtype=np.float32)
    
    final_top_y_diff = 0.0  # Now they're at the same y
    
    print(f"    Unified endpoints: TL=({TL_new[0]:.1f}, {TL_new[1]:.1f}), TR=({TR_new[0]:.1f}, {TR_new[1]:.1f})")
    
    return TL_new, TR_new, BL, BR, "line_equation_unified", final_top_y_diff, unified_y_top, unified_y_top


def enforce_paired_top_constraint_yquant(L_inliers: np.ndarray, R_inliers: np.ndarray,
                                          L_p0: np.ndarray, L_d: np.ndarray,
                                          R_p0: np.ndarray, R_d: np.ndarray,
                                          top_pct_init: float, bot_pct: float,
                                          max_top_y_diff: float):
    """
    Compute endpoints with paired-top constraint: TL.y and TR.y should be close.
    If |TL.y - TR.y| > max_top_y_diff, iteratively tighten top_pct until satisfied.
    (Legacy method - kept for compatibility)
    
    Returns:
        TL, TR, BL, BR, used_top_pct, final_top_y_diff, yL_top, yR_top
    """
    top_pct = top_pct_init
    min_top_pct = 0.1  # Don't go below this
    shrink_factor = 0.6  # Multiply top_pct by this each iteration

    yL_top, yR_top = None, None

    for attempt in range(20):  # Max iterations
        # Compute endpoints for left line
        TL, BL, yL_top, yL_bot = compute_endpoints_yquant(L_inliers, L_p0, L_d, top_pct, bot_pct)
        if TL is None:
            return None, None, None, None, top_pct, None, None, None

        # Compute endpoints for right line
        TR, BR, yR_top, yR_bot = compute_endpoints_yquant(R_inliers, R_p0, R_d, top_pct, bot_pct)
        if TR is None:
            return None, None, None, None, top_pct, None, None, None

        # Check paired-top constraint
        top_y_diff = abs(yL_top - yR_top)
        
        if top_y_diff <= max_top_y_diff:
            # Constraint satisfied
            return TL, TR, BL, BR, top_pct, top_y_diff, yL_top, yR_top

        # Tighten top percentile
        if top_pct <= min_top_pct:
            # Can't tighten further, return current best
            print(f"[WARNING] Paired-top constraint not satisfied after tightening. "
                  f"Final top_y_diff={top_y_diff:.1f}px (threshold={max_top_y_diff})")
            return TL, TR, BL, BR, top_pct, top_y_diff, yL_top, yR_top

        top_pct *= shrink_factor
        top_pct = max(top_pct, min_top_pct)

    # Should not reach here
    return None, None, None, None, top_pct, None, None, None


# ========================================================================
# Visualization Utilities
# ========================================================================

def overlay_points(shape, points: np.ndarray, color=255):
    """Create visualization of points on black background."""
    vis = np.zeros(shape, dtype=np.uint8)
    pts_int = points.astype(np.int32)
    for pt in pts_int:
        if 0 <= pt[1] < shape[0] and 0 <= pt[0] < shape[1]:
            vis[pt[1], pt[0]] = color
    return vis


def draw_line_on_image(img: np.ndarray, p0: np.ndarray, d: np.ndarray, color, thickness=2):
    """Draw infinite line on image."""
    H, W = img.shape[:2]
    # Extend line to image boundaries
    t_max = max(W, H) * 2
    pt1 = (p0 - t_max * d).astype(np.int32)
    pt2 = (p0 + t_max * d).astype(np.int32)
    cv2.line(img, tuple(pt1), tuple(pt2), color, thickness, cv2.LINE_AA)


def draw_point(img: np.ndarray, pt: np.ndarray, color, radius=8, thickness=3):
    """Draw point marker on image."""
    pt_int = tuple(pt.astype(np.int32))
    cv2.circle(img, pt_int, radius, color, thickness, cv2.LINE_AA)


# ========================================================================
# Main Pipeline
# ========================================================================

def estimate_4pts_from_mask(mask255: np.ndarray, base_vis: np.ndarray, 
                             out_dir: Path, args):
    """
    Main pipeline to estimate 4 corner points from binary mask.
    
    **BOTTOM-UP SIDELINE EXTRACTION APPROACH**
    
    Key Insight:
    - Bottom of court (near floor) has minimal advertisement noise
    - Sidelines are reliably the extreme x positions at the bottom
    - Use bottom region as "seed" and extend upward
    
    Steps:
    1) Build side-line support mask with horizontal removal
    2) Extract all mask points, split into left/right halves
    3) **BOTTOM-UP EXTRACTION:**
       a) Extract seed points from bottom region (extreme x in each y-band)
       b) Fit seed line from bottom points
       c) Extend upward: keep points close to seed line AND at extreme x
    4) Compute endpoints using y-quantiles with paired-top constraint
    5) Save all intermediate outputs
    
    Returns:
        Dictionary with keys TL, TR, BR, BL (each value is np.array([x, y]))
    """
    H, W = mask255.shape[:2]

    # Step 1: Build side-line support mask
    print("\n[STEP 1] Building side-line support mask...")
    
    # Apply optional opening/dilation
    mask_cleaned = build_sideline_support_mask(mask255, out_dir, "01", 
                                                args.open_ks, args.dilate_ks)
    save_image(out_dir, "01_mask_cleaned", mask_cleaned)

    # Remove horizontal components (net, service lines)
    print("[STEP 2] Removing horizontal components...")
    mask_sidelines, horiz_extracted = remove_horizontal_components(
        mask_cleaned, out_dir, "02",
        horiz_kernel_ratio=args.horiz_kernel_ratio,
        horiz_iter=args.horiz_iter,
        central_band_only=args.horiz_central_band_only,
        band_y0_ratio=args.horiz_band_y0_ratio,
        band_y1_ratio=args.horiz_band_y1_ratio
    )

    # Step 2: Extract ALL mask points
    print("[STEP 3] Extracting all mask points...")
    points = get_ransac_points(mask_sidelines, args.use_edge_points, 
                               args.max_points, out_dir, "03")

    # Split into left and right halves (simple 50% split)
    split_x = W * 0.5
    left_mask = points[:, 0] < split_x
    right_mask = points[:, 0] >= split_x
    
    left_points = points[left_mask]
    right_points = points[right_mask]
    
    print(f"  Split at x={split_x:.0f}: Left={len(left_points)}, Right={len(right_points)}")

    # =====================================================================
    # Step 3: BOTTOM-UP SIDELINE EXTRACTION
    # =====================================================================
    print("\n[STEP 4] Bottom-Up Sideline Extraction...")
    
    # Left sideline
    L_p0, L_d, L_n, L_pts = bottom_up_sideline_extraction(
        points=left_points,
        H=H,
        region_type='left',
        bottom_ratio=args.bottom_ratio,
        seed_y_bin=args.seed_y_bin,
        seed_tolerance=args.seed_tolerance,
        extend_dist_th=args.extend_dist_th,
        extend_x_tolerance=args.extend_x_tolerance,
        continuity_th=args.continuity_th,
        extend_y_bin=args.extend_y_bin,
        k_neighbors=args.k_neighbors,
        linearity_th=args.linearity_th,
        out_dir=out_dir,
        debug_prefix="04_left"
    )
    
    # Right sideline
    R_p0, R_d, R_n, R_pts = bottom_up_sideline_extraction(
        points=right_points,
        H=H,
        region_type='right',
        bottom_ratio=args.bottom_ratio,
        seed_y_bin=args.seed_y_bin,
        seed_tolerance=args.seed_tolerance,
        extend_dist_th=args.extend_dist_th,
        extend_x_tolerance=args.extend_x_tolerance,
        continuity_th=args.continuity_th,
        extend_y_bin=args.extend_y_bin,
        k_neighbors=args.k_neighbors,
        linearity_th=args.linearity_th,
        out_dir=out_dir,
        debug_prefix="04_right"
    )

    print(f"\n[STEP 4] Extraction complete:")
    print(f"  Left sideline: {len(L_pts)} points")
    print(f"  Right sideline: {len(R_pts)} points")
    
    # Save final point visualizations
    save_image(out_dir, "05_left_line_final", overlay_points(mask255.shape, L_pts))
    save_image(out_dir, "05_right_line_final", overlay_points(mask255.shape, R_pts))
    
    # Combined visualization (black background)
    vis_both = np.zeros((H, W, 3), dtype=np.uint8)
    for pt in L_pts.astype(np.int32):
        if 0 <= pt[1] < H and 0 <= pt[0] < W:
            vis_both[pt[1], pt[0]] = (255, 255, 0)  # Cyan
    for pt in R_pts.astype(np.int32):
        if 0 <= pt[1] < H and 0 <= pt[0] < W:
            vis_both[pt[1], pt[0]] = (0, 255, 255)  # Yellow
    save_image(out_dir, "05_both_sidelines", vis_both)
    
    # NEW: Overlay detected points on original image
    vis_pts_overlay = to_bgr(base_vis.copy())
    # Draw points with larger radius for visibility
    for pt in L_pts.astype(np.int32):
        if 0 <= pt[1] < H and 0 <= pt[0] < W:
            cv2.circle(vis_pts_overlay, (pt[0], pt[1]), 2, (255, 255, 0), -1)  # Cyan filled
    for pt in R_pts.astype(np.int32):
        if 0 <= pt[1] < H and 0 <= pt[0] < W:
            cv2.circle(vis_pts_overlay, (pt[0], pt[1]), 2, (0, 255, 255), -1)  # Yellow filled
    save_image(out_dir, "05_detected_points_overlay", vis_pts_overlay)

    # Visualize both fitted lines
    vis_lines = to_bgr(base_vis.copy())
    draw_line_on_image(vis_lines, L_p0, L_d, (0, 255, 255), thickness=3)  # Cyan
    draw_line_on_image(vis_lines, R_p0, R_d, (255, 255, 0), thickness=3)  # Yellow
    save_image(out_dir, "06_fitted_lines_overlay", vis_lines)

    # Step 6: Compute endpoints using LINE EQUATION (IMPROVED!)
    print("[STEP 6] Computing endpoints using line equation extrapolation...")
    
    if args.use_line_equation:
        # New method: Line equation based extrapolation
        TL, TR, BL, BR, method_info, top_dy, yL_top, yR_top = enforce_paired_top_constraint_line_equation(
            L_inliers=L_pts,
            R_inliers=R_pts,
            L_p0=L_p0, L_d=L_d,
            R_p0=R_p0, R_d=R_d,
            H=H, W=W,
            top_margin=args.top_margin,
            bot_margin=args.bot_margin,
            max_top_y_diff=args.max_top_y_diff,
            use_extrapolation=args.use_extrapolation
        )
        print(f"  Method: {method_info}")
    else:
        # Legacy method: Y-percentile based
        TL, TR, BL, BR, method_info, top_dy, yL_top, yR_top = enforce_paired_top_constraint_yquant(
            L_inliers=L_pts,
            R_inliers=R_pts,
            L_p0=L_p0, L_d=L_d,
            R_p0=R_p0, R_d=R_d,
            top_pct_init=args.top_pct,
            bot_pct=args.bot_pct,
            max_top_y_diff=args.max_top_y_diff
        )
        print(f"  Method: y_percentile (top_pct={method_info:.3f}%)")

    if TL is None:
        raise RuntimeError(
            "Endpoint computation failed. "
            "Try adjusting parameters or checking mask quality."
        )

    print(f"  Top y-diff: {top_dy:.1f}px (max allowed: {args.max_top_y_diff}px)")
    if yL_top is not None and yR_top is not None:
        print(f"  TL.y={yL_top:.1f}, TR.y={yR_top:.1f}")

    # Visualize y-threshold debug info
    vis_thr = to_bgr(base_vis.copy())
    cv2.putText(vis_thr, f"method={method_info}, top_dy={top_dy:.1f}px", 
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (230, 230, 230), 2, cv2.LINE_AA)
    
    if yL_top is not None and yR_top is not None:
        cv2.line(vis_thr, (0, int(yL_top)), (W-1, int(yL_top)), (255, 255, 0), 2, cv2.LINE_AA)
        cv2.line(vis_thr, (0, int(yR_top)), (W-1, int(yR_top)), (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis_thr, f"L y_top={yL_top:.1f}", (20, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(vis_thr, f"R y_top={yR_top:.1f}", (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
    
    save_image(out_dir, "07_top_threshold_debug", vis_thr)

    # Step 7: Save final visualizations
    print("[STEP 7] Saving final outputs...")
    
    # Endpoints overlay
    vis_endpoints = to_bgr(base_vis.copy())
    draw_line_on_image(vis_endpoints, L_p0, L_d, (0, 255, 255), thickness=3)
    draw_line_on_image(vis_endpoints, R_p0, R_d, (255, 255, 0), thickness=3)
    
    draw_point(vis_endpoints, TL, (0, 0, 255))     # Red
    draw_point(vis_endpoints, TR, (0, 255, 0))     # Green
    draw_point(vis_endpoints, BL, (0, 0, 255))     # Red
    draw_point(vis_endpoints, BR, (0, 255, 0))     # Green
    
    save_image(out_dir, "08_endpoints_overlay", vis_endpoints)

    # Quadrilateral overlay
    vis_quad = vis_endpoints.copy()
    quad = np.array([TL, TR, BR, BL], dtype=np.int32)
    cv2.polylines(vis_quad, [quad], True, (255, 0, 255), 3, cv2.LINE_AA)  # Magenta
    save_image(out_dir, "09_quad_overlay", vis_quad)

    # Save coordinates to text files
    pts_dict = {"TL": TL, "TR": TR, "BR": BR, "BL": BL}

    # Detailed text file
    txt = out_dir / "estimated_4points.txt"
    with open(txt, "w") as f:
        f.write("Estimated 4 points from side-lines only (Bottom-Up + Line Equation)\n")
        f.write(f"Method: {method_info}\n")
        f.write(f"Bottom ratio: {args.bottom_ratio} (seed from bottom {args.bottom_ratio*100:.0f}%)\n")
        f.write(f"Seed params: y_bin={args.seed_y_bin}, tolerance={args.seed_tolerance}\n")
        f.write(f"Extend params: dist_th={args.extend_dist_th}, x_tol={args.extend_x_tolerance}\n")
        f.write(f"Continuity params: threshold={args.continuity_th}, y_bin={args.extend_y_bin}\n")
        f.write(f"Linearity params: k_neighbors={args.k_neighbors}, threshold={args.linearity_th}\n")
        f.write(f"Endpoint params: top_margin={args.top_margin}, bot_margin={args.bot_margin}\n")
        f.write(f"top_y_diff: {top_dy:.3f}px\n")
        f.write(f"left_points: {len(L_pts)}\n")
        f.write(f"right_points: {len(R_pts)}\n")
        for k in ["TL", "TR", "BR", "BL"]:
            p = pts_dict[k]
            f.write(f"{k}: {float(p[0]):.6f}, {float(p[1]):.6f}\n")
    
    print(f"[SAVED] {txt}")

    # Compact JSON-like file
    txt2 = out_dir / "estimated_4points_compact.txt"
    with open(txt2, "w") as f:
        f.write(
            "{"
            + ", ".join([
                f'"{k}":[{float(pts_dict[k][0]):.3f},{float(pts_dict[k][1]):.3f}]' 
                for k in ["TL", "TR", "BR", "BL"]
            ])
            + "}\n"
        )
    
    print(f"[SAVED] {txt2}")

    return pts_dict


# ========================================================================
# Main Entry Point
# ========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Estimate TL/TR/BR/BL using only 2 outer side-lines from binary mask. "
                    "Uses Two-Stage refinement to handle advertisement noise."
    )
    
    # Required I/O arguments
    parser.add_argument("--mask_input", required=True, 
                        help="Path to binary mask image (court lines white on black).")
    parser.add_argument("--original_input", default=None,
                        help="(Optional) Path to original RGB frame for nicer overlay visualizations.")
    parser.add_argument("--out_root", required=True,
                        help="Root directory to save results. A timestamped run folder will be created.")

    # Preprocessing parameters
    parser.add_argument("--open_ks", type=int, default=0,
                        help="Opening kernel size (odd). 0 to disable. Removes small noise.")
    parser.add_argument("--dilate_ks", type=int, default=3,
                        help="Dilation kernel size (odd). 0 to disable. Strengthens line support.")
    parser.add_argument("--use_edge_points", action="store_true",
                        help="Use morphological gradient edge pixels for RANSAC instead of mask pixels.")

    # Horizontal removal parameters
    parser.add_argument("--horiz_kernel_ratio", type=float, default=0.25,
                        help="Horizontal kernel length as ratio of image width for extracting horizontal components.")
    parser.add_argument("--horiz_iter", type=int, default=1,
                        help="Number of morphological opening iterations for horizontal extraction.")
    parser.add_argument("--horiz_central_band_only", action="store_true",
                        help="If set, only remove horizontal components within central y-band (net-focused).")
    parser.add_argument("--horiz_band_y0_ratio", type=float, default=0.40,
                        help="Central band top y-coordinate as ratio of image height.")
    parser.add_argument("--horiz_band_y1_ratio", type=float, default=0.70,
                        help="Central band bottom y-coordinate as ratio of image height.")

    # Initial RANSAC parameters
    parser.add_argument("--dist_th", type=float, default=3.5,
                        help="Inlier distance threshold in pixels for initial RANSAC.")
    parser.add_argument("--ransac_iter", type=int, default=2500,
                        help="Number of RANSAC iterations per line for initial detection.")
    parser.add_argument("--min_inliers", type=int, default=450,
                        help="Minimum number of inliers to accept a line in initial RANSAC.")
    parser.add_argument("--max_points", type=int, default=120000,
                        help="Maximum sampled points for RANSAC (downsampled if exceeded).")
    
    # Split-region RANSAC parameter
    parser.add_argument("--split_x_ratio", type=float, default=0.5,
                        help="X-coordinate ratio to split left/right regions for RANSAC (default 0.5 = middle).")
    
    # Length-based filtering
    parser.add_argument("--length_weight", type=float, default=0.7,
                        help="Weight for length-based scoring in initial RANSAC (0.0-1.0).")

    # Vertical orientation constraints
    parser.add_argument("--forbid_horizontal_deg", type=float, default=0.0,
                        help="Reject lines within this angle (degrees) of horizontal. Set to 0 to disable.")
    parser.add_argument("--prefer_vertical_deg", type=float, default=90.0,
                        help="Acceptable deviation from vertical: |angle - 90°| <= this value.")
    parser.add_argument("--enforce_vertical", action="store_true",
                        help="If set, only accept near-vertical lines in initial RANSAC.")

    # =====================================================================
    # Bottom-Up Sideline Extraction Parameters (KEY!)
    # =====================================================================
    parser.add_argument("--bottom_ratio", type=float, default=0.25,
                        help="Use bottom X%% of image for seed extraction (default 25%%). "
                             "Increase if bottom region is noisy.")
    parser.add_argument("--seed_y_bin", type=int, default=10,
                        help="Y-band size for seed point extraction (pixels).")
    parser.add_argument("--seed_tolerance", type=float, default=10.0,
                        help="X-tolerance for seed point selection (pixels).")
    parser.add_argument("--extend_dist_th", type=float, default=8.0,
                        help="Max perpendicular distance from seed line when extending (pixels).")
    parser.add_argument("--extend_x_tolerance", type=float, default=15.0,
                        help="X-tolerance around expected position when extending (pixels).")
    parser.add_argument("--continuity_th", type=float, default=25.0,
                        help="Max allowed x-jump between adjacent y-bands (pixels). "
                             "Smaller = stricter continuity check, filters more noise.")
    parser.add_argument("--extend_y_bin", type=int, default=15,
                        help="Y-band size for extension process (pixels).")
    
    # Local Linearity Filter Parameters (NEW!)
    parser.add_argument("--k_neighbors", type=int, default=12,
                        help="Number of neighbors for local linearity check. "
                             "Larger = considers more context, but slower.")
    parser.add_argument("--linearity_th", type=float, default=4.0,
                        help="Max residual threshold for linearity filter (pixels). "
                             "Smaller = stricter, removes more noise but may lose line points.")

    # Endpoint computation parameters
    parser.add_argument("--top_pct", type=float, default=3.0,
                        help="(Legacy) Initial top y-percentile for upper endpoints. Range: 0-100.")
    parser.add_argument("--bot_pct", type=float, default=97.0,
                        help="(Legacy) Bottom y-percentile for lower endpoints. Range: 0-100.")
    parser.add_argument("--max_top_y_diff", type=float, default=90.0,
                        help="Maximum allowed |TL.y - TR.y| in pixels.")
    
    # Line Equation Based Endpoint Parameters (NEW - IMPROVED!)
    parser.add_argument("--use_line_equation", action="store_true", default=True,
                        help="Use line equation extrapolation for endpoints (recommended). "
                             "Set --no_line_equation to use legacy percentile method.")
    parser.add_argument("--no_line_equation", dest="use_line_equation", action="store_false",
                        help="Disable line equation method, use legacy y-percentile method.")
    parser.add_argument("--use_extrapolation", action="store_true", default=True,
                        help="Extrapolate line beyond detected points to capture full extent.")
    parser.add_argument("--no_extrapolation", dest="use_extrapolation", action="store_false",
                        help="Disable extrapolation, use only detected point range.")
    parser.add_argument("--top_margin", type=float, default=0.02,
                        help="Margin from top of image as ratio (0.02 = 2%%). "
                             "Smaller = endpoints closer to image top.")
    parser.add_argument("--bot_margin", type=float, default=0.02,
                        help="Margin from bottom of image as ratio (0.02 = 2%%).")

    args = parser.parse_args()

    # Validate inputs
    mask_path = Path(args.mask_input)
    if not mask_path.exists():
        raise FileNotFoundError(f"Mask image not found: {mask_path}")

    # Load mask
    mask_in = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
    if mask_in is None:
        raise ValueError(f"Failed to read mask image: {mask_path}")

    # Create output directory
    out_dir = make_output_dir(args.out_root)
    print(f"[INFO] Output directory: {out_dir}")

    # Normalize mask
    mask255 = normalize_mask_to_255(mask_in)
    save_image(out_dir, "00_mask_input_normalized", mask255)

    H, W = mask255.shape[:2]
    print(f"[INFO] Mask dimensions: {W}x{H}")

    # Load or create base visualization image
    if args.original_input is not None:
        orig_path = Path(args.original_input)
        if not orig_path.exists():
            raise FileNotFoundError(f"Original image not found: {orig_path}")
        
        base = cv2.imread(str(orig_path), cv2.IMREAD_COLOR)
        if base is None:
            raise ValueError(f"Failed to read original image: {orig_path}")
        
        # Resize if dimensions don't match
        if base.shape[0] != H or base.shape[1] != W:
            base = cv2.resize(base, (W, H), interpolation=cv2.INTER_LINEAR)
        
        save_image(out_dir, "00_original_for_overlay", base)
    else:
        # Use mask as base visualization
        base = to_bgr(mask255)
        save_image(out_dir, "00_overlay_base_from_mask", base)

    # Run main pipeline
    try:
        pts = estimate_4pts_from_mask(mask255, base, out_dir, args)
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        print(f"[INFO] Partial results saved to: {out_dir}")
        raise

    # Print final results
    print("\n" + "="*60)
    print("[RESULT] Estimated 4 corner points (pixel coordinates):")
    print("="*60)
    for k in ["TL", "TR", "BR", "BL"]:
        p = pts[k]
        print(f"  {k}: ({float(p[0]):.2f}, {float(p[1]):.2f})")
    
    print(f"\n[DONE] All outputs saved to: {out_dir}")
    print("="*60)


if __name__ == "__main__":
    main()


"""
Example Usage:

# Basic usage - Bottom-Up with Line Equation Extrapolation (recommended)
python pl_1_ransac_cld_split_btu_ll.py \
  --mask_input source_image/pro_mask_m_rm.png \
  --original_input source_image/pro_court.png \
  --out_root results_bottomup_ll_v2

# Adjust endpoint margins (for different camera angles)
python pl_1_ransac_twostage.py \
  --mask_input source_image/pro_mask_m_rm.png \
  --original_input source_image/pro_court.png \
  --out_root results_bottomup \
  --top_margin 0.01 \
  --bot_margin 0.01

# Use legacy percentile method (if line equation doesn't work well)
python pl_1_ransac_twostage.py \
  --mask_input source_image/pro_mask_m_rm.png \
  --original_input source_image/pro_court.png \
  --out_root results_bottomup \
  --no_line_equation \
  --top_pct 1.0

# Stricter linearity filter (for heavy advertisement noise)
python pl_1_ransac_twostage.py \
  --mask_input source_image/pro_mask_m_rm.png \
  --original_input source_image/pro_court.png \
  --out_root results_bottomup \
  --linearity_th 3.0 \
  --k_neighbors 15

# Full example with all relevant parameters
python pl_1_ransac_twostage.py \
  --mask_input source_image/pro_mask_m_rm.png \
  --original_input source_image/pro_court.png \
  --out_root results_bottomup \
  --open_ks 0 \
  --dilate_ks 3 \
  --horiz_kernel_ratio 0.25 \
  --horiz_iter 1 \
  --bottom_ratio 0.25 \
  --seed_y_bin 10 \
  --seed_tolerance 10.0 \
  --extend_dist_th 8.0 \
  --extend_x_tolerance 15.0 \
  --continuity_th 25.0 \
  --extend_y_bin 15 \
  --k_neighbors 12 \
  --linearity_th 4.0 \
  --top_margin 0.02 \
  --bot_margin 0.02 \
  --max_top_y_diff 60
"""