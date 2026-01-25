#!/usr/bin/env python3
"""
Badminton Court 4-Point Estimator (Side-lines only) - Robust Pipeline

Goal:
- Input: Binary-ish mask image where court lines are white on black
- Output: TL/TR/BR/BL (top-left, top-right, bottom-right, bottom-left) endpoints in pixel coords
- Objective: Robustly estimate ONLY the two outer side lines of a badminton court

Pipeline:
  1) Normalize mask to 0/255 binary
  2) Build side-line-only mask with horizontal component removal
  3) Extract points from side-line mask for RANSAC
  4) Fit exactly two near-vertical lines (left/right side lines) via Sequential RANSAC
  5) Compute endpoints using y-quantiles with paired-top constraint
  6) Save all intermediate outputs and final coordinates

Usage:
python pl_1_ransac.py \
  --mask_input path/to/mask.png \
  --out_root results_dir

Optional original frame for overlay:
python pl_1_ransac.py \
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


def ransac_single_line(points: np.ndarray, dist_th: float, max_iter: int, min_inliers: int,
                       forbid_horizontal_deg: float, prefer_vertical_deg: float,
                       enforce_vertical: bool):
    """
    Fit a single line using RANSAC.
    
    Args:
        points: Nx2 array of (x, y) coordinates
        dist_th: Inlier distance threshold in pixels
        max_iter: Maximum RANSAC iterations
        min_inliers: Minimum number of inliers to accept a line
        forbid_horizontal_deg: Reject lines within this angle of horizontal
        prefer_vertical_deg: Acceptable deviation from vertical (90°)
        enforce_vertical: If True, only accept near-vertical lines
    
    Returns:
        (p0, direction, normal, inlier_mask) or None if failed
    """
    n_pts = points.shape[0]
    if n_pts < max(200, min_inliers):
        return None

    best_inliers = None
    best_count = 0
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
        if is_near_horizontal(d, forbid_horizontal_deg):
            continue  # Reject horizontal lines

        if enforce_vertical and not is_near_vertical(d, prefer_vertical_deg):
            continue  # Enforce vertical constraint

        # Count inliers
        dists = point_line_dist(points, p0, n)
        inliers = dists < dist_th
        count = np.sum(inliers)

        # Update best model
        if count > best_count:
            best_count = count
            best_inliers = inliers
            best_model = model

    # Check if we found a good line
    if best_model is None or best_count < min_inliers:
        return None

    # Refine using cv2.fitLine on inliers
    p0, d, n = best_model
    inlier_pts = points[best_inliers]
    
    # fitLine returns [vx, vy, x0, y0]
    line_params = cv2.fitLine(inlier_pts, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy = float(line_params[0]), float(line_params[1])
    x0, y0 = float(line_params[2]), float(line_params[3])
    
    # Normalize direction
    norm = np.sqrt(vx*vx + vy*vy)
    if norm > 1e-6:
        d_refined = np.array([vx/norm, vy/norm], dtype=np.float32)
        n_refined = np.array([-d_refined[1], d_refined[0]], dtype=np.float32)
        p0_refined = np.array([x0, y0], dtype=np.float32)
    else:
        # Fallback to RANSAC model
        d_refined, n_refined, p0_refined = d, n, p0

    # Recompute inliers with refined model
    dists_refined = point_line_dist(points, p0_refined, n_refined)
    inliers_refined = dists_refined < dist_th

    return p0_refined, d_refined, n_refined, inliers_refined


def ransac_two_lines_split_region(points: np.ndarray, W: int, 
                                   dist_th: float, max_iter: int, min_inliers: int,
                                   forbid_horizontal_deg: float, prefer_vertical_deg: float,
                                   enforce_vertical: bool, split_ratio: float = 0.5):
    """
    Fit two lines by splitting points into left and right regions.
    This avoids detecting center line by forcing RANSAC to work in separate regions.
    
    Args:
        points: Nx2 array of (x, y) coordinates
        W: Image width
        split_ratio: X-coordinate ratio to split left/right regions (default 0.5 = middle)
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
        forbid_horizontal_deg, prefer_vertical_deg, enforce_vertical
    )
    
    if left_fit is None:
        raise RuntimeError("RANSAC failed in left region. Try relaxing constraints or check left side mask quality.")
    
    p0_left, d_left, n_left, inliers_left_local = left_fit
    print(f"  Left line: {np.sum(inliers_left_local)} inliers")
    
    # Fit line in right region
    print("[INFO] Fitting line in RIGHT region...")
    right_fit = ransac_single_line(
        right_points, dist_th, max_iter, min_inliers,
        forbid_horizontal_deg, prefer_vertical_deg, enforce_vertical
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


def ransac_two_lines_sequential(points: np.ndarray, dist_th: float, max_iter: int,
                                  min_inliers: int, forbid_horizontal_deg: float,
                                  prefer_vertical_deg: float, enforce_vertical: bool):
    """
    Fit two lines using Sequential RANSAC:
    1) Fit first line
    2) Remove its inliers
    3) Fit second line from remaining points
    
    NOTE: This method may detect center line first. Use ransac_two_lines_split_region instead.
    
    Returns:
        ((p01, d1, n1, inliers1), (p02, d2, n2, inliers2)) or None if failed
    """
    # Fit first line
    fit1 = ransac_single_line(points, dist_th, max_iter, min_inliers,
                               forbid_horizontal_deg, prefer_vertical_deg, enforce_vertical)
    if fit1 is None:
        return None
    
    p01, d1, n1, inliers1 = fit1

    # Remove first line's inliers
    remaining_points = points[~inliers1]
    
    if len(remaining_points) < min_inliers:
        return None

    # Fit second line
    fit2 = ransac_single_line(remaining_points, dist_th, max_iter, min_inliers,
                               forbid_horizontal_deg, prefer_vertical_deg, enforce_vertical)
    if fit2 is None:
        return None
    
    p02, d2, n2, inliers2_local = fit2

    # Convert local inliers mask back to original indexing
    inliers2 = np.zeros(len(points), dtype=bool)
    remaining_indices = np.where(~inliers1)[0]
    inliers2[remaining_indices[inliers2_local]] = True

    return (p01, d1, n1, inliers1), (p02, d2, n2, inliers2)


# ========================================================================
# E) Endpoint Computation with Y-Quantiles
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


def compute_endpoints_yquant(inlier_pts: np.ndarray, p0: np.ndarray, d: np.ndarray,
                              top_pct: float, bot_pct: float):
    """
    Compute line endpoints using y-percentiles of inlier points.
    
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


def enforce_paired_top_constraint_yquant(L_inliers: np.ndarray, R_inliers: np.ndarray,
                                          L_p0: np.ndarray, L_d: np.ndarray,
                                          R_p0: np.ndarray, R_d: np.ndarray,
                                          top_pct_init: float, bot_pct: float,
                                          max_top_y_diff: float):
    """
    Compute endpoints with paired-top constraint: TL.y and TR.y should be close.
    If |TL.y - TR.y| > max_top_y_diff, iteratively tighten top_pct until satisfied.
    
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
    vis[pts_int[:, 1], pts_int[:, 0]] = color
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
    
    Steps:
    1) Build side-line support mask with horizontal removal
    2) Extract RANSAC points
    3) Fit two side lines using Sequential RANSAC
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

    # Step 2: Extract RANSAC points
    print("[STEP 3] Extracting RANSAC point set...")
    points = get_ransac_points(mask_sidelines, args.use_edge_points, 
                               args.max_points, out_dir, "03")

    # Step 3: Fit two side lines using Split-Region RANSAC
    print("[STEP 4] Fitting two side lines via Split-Region RANSAC...")
    
    result = ransac_two_lines_split_region(
        points=points,
        W=W,
        dist_th=args.dist_th,
        max_iter=args.ransac_iter,
        min_inliers=args.min_inliers,
        forbid_horizontal_deg=args.forbid_horizontal_deg,
        prefer_vertical_deg=args.prefer_vertical_deg,
        enforce_vertical=args.enforce_vertical,
        split_ratio=args.split_x_ratio
    )

    if result is None:
        raise RuntimeError(
            "Split-Region RANSAC failed to find two side lines. "
            "Try relaxing: --enforce_vertical, --prefer_vertical_deg, "
            "--dist_th, --min_inliers, or check mask quality."
        )

    (p0_left, d_left, n_left, inliers_left), (p0_right, d_right, n_right, inliers_right) = result

    # Extract inlier points
    pts_left = points[inliers_left]
    pts_right = points[inliers_right]

    print(f"  Left line: {np.sum(inliers_left)} inliers")
    print(f"  Right line: {np.sum(inliers_right)} inliers")

    # Save inlier visualizations
    save_image(out_dir, "04_left_line_inliers", overlay_points(mask255.shape, pts_left))
    save_image(out_dir, "04_right_line_inliers", overlay_points(mask255.shape, pts_right))

    # Visualize both fitted lines
    vis_both = to_bgr(base_vis.copy())
    draw_line_on_image(vis_both, p0_left, d_left, (0, 255, 255), thickness=3)  # Cyan
    draw_line_on_image(vis_both, p0_right, d_right, (255, 255, 0), thickness=3)  # Yellow
    save_image(out_dir, "05_two_lines_overlay", vis_both)

    # Assign left/right (already determined by split_region)
    L_p0, L_d, L_pts = p0_left, d_left, pts_left
    R_p0, R_d, R_pts = p0_right, d_right, pts_right

    print(f"[STEP 5] Left and right lines determined by region split")
    save_image(out_dir, "06_left_line_inliers_final", overlay_points(mask255.shape, L_pts))
    save_image(out_dir, "06_right_line_inliers_final", overlay_points(mask255.shape, R_pts))

    # Step 5: Compute endpoints with paired-top constraint
    print("[STEP 6] Computing endpoints with y-quantiles and paired-top constraint...")
    
    TL, TR, BL, BR, used_top_pct, top_dy, yL_top, yR_top = enforce_paired_top_constraint_yquant(
        L_inliers=L_pts,
        R_inliers=R_pts,
        L_p0=L_p0, L_d=L_d,
        R_p0=R_p0, R_d=R_d,
        top_pct_init=args.top_pct,
        bot_pct=args.bot_pct,
        max_top_y_diff=args.max_top_y_diff
    )

    if TL is None:
        raise RuntimeError(
            "Endpoint computation failed. "
            "Try increasing --min_inliers, relaxing --enforce_vertical, "
            "or checking mask quality."
        )

    print(f"  Used top_pct: {used_top_pct:.3f}%")
    print(f"  Top y-diff: {top_dy:.1f}px (max allowed: {args.max_top_y_diff}px)")

    # Visualize y-threshold debug info
    vis_thr = to_bgr(base_vis.copy())
    cv2.putText(vis_thr, f"used_top_pct={used_top_pct:.3f}, top_dy={top_dy:.1f}px", 
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (230, 230, 230), 2, cv2.LINE_AA)
    
    if yL_top is not None and yR_top is not None:
        cv2.line(vis_thr, (0, int(yL_top)), (W-1, int(yL_top)), (255, 255, 0), 2, cv2.LINE_AA)
        cv2.line(vis_thr, (0, int(yR_top)), (W-1, int(yR_top)), (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis_thr, f"L y_top={yL_top:.1f}", (20, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(vis_thr, f"R y_top={yR_top:.1f}", (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
    
    save_image(out_dir, "07_top_threshold_debug", vis_thr)

    # Step 6: Save final visualizations
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
        f.write("Estimated 4 points from side-lines only (Split-Region RANSAC)\n")
        f.write(f"Method: Left/Right region split at x={args.split_x_ratio*W:.1f} (ratio={args.split_x_ratio:.2f})\n")
        f.write(f"used_top_pct: {used_top_pct:.6f}\n")
        f.write(f"top_y_diff: {top_dy:.3f}px\n")
        f.write(f"horiz_kernel_ratio: {args.horiz_kernel_ratio:.3f}\n")
        f.write(f"horiz_iter: {args.horiz_iter}\n")
        f.write(f"horiz_central_band_only: {args.horiz_central_band_only}\n")
        f.write(f"prefer_vertical_deg: {args.prefer_vertical_deg:.2f}\n")
        f.write(f"enforce_vertical: {args.enforce_vertical}\n")
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
        description="Estimate TL/TR/BR/BL using only 2 outer side-lines from binary mask."
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
                        help="Horizontal kernel length as ratio of image width for extracting horizontal components (e.g., 0.25).")
    parser.add_argument("--horiz_iter", type=int, default=1,
                        help="Number of morphological opening iterations for horizontal extraction.")
    parser.add_argument("--horiz_central_band_only", action="store_true",
                        help="If set, only remove horizontal components within central y-band (net-focused).")
    parser.add_argument("--horiz_band_y0_ratio", type=float, default=0.40,
                        help="Central band top y-coordinate as ratio of image height (only if horiz_central_band_only).")
    parser.add_argument("--horiz_band_y1_ratio", type=float, default=0.70,
                        help="Central band bottom y-coordinate as ratio of image height (only if horiz_central_band_only).")

    # RANSAC parameters
    parser.add_argument("--dist_th", type=float, default=3.5,
                        help="Inlier distance threshold in pixels.")
    parser.add_argument("--ransac_iter", type=int, default=2500,
                        help="Number of RANSAC iterations per line.")
    parser.add_argument("--min_inliers", type=int, default=450,
                        help="Minimum number of inliers to accept a line.")
    parser.add_argument("--max_points", type=int, default=120000,
                        help="Maximum sampled points for RANSAC (downsampled if exceeded).")
    
    # Split-region RANSAC parameter
    parser.add_argument("--split_x_ratio", type=float, default=0.5,
                        help="X-coordinate ratio to split left/right regions for RANSAC (default 0.5 = middle).")

    # Vertical orientation constraints
    parser.add_argument("--forbid_horizontal_deg", type=float, default=15.0,
                        help="Reject lines within this angle (degrees) of horizontal (0° or 180°).")
    parser.add_argument("--prefer_vertical_deg", type=float, default=25.0,
                        help="Acceptable deviation from vertical: |angle - 90°| <= this value.")
    parser.add_argument("--enforce_vertical", action="store_true",
                        help="If set, only accept near-vertical lines (recommended for side-line detection).")

    # Endpoint computation parameters
    parser.add_argument("--top_pct", type=float, default=3.0,
                        help="Initial top y-percentile for upper endpoints (smaller = higher up). Range: 0-100.")
    parser.add_argument("--bot_pct", type=float, default=97.0,
                        help="Bottom y-percentile for lower endpoints (larger = lower down). Range: 0-100.")
    parser.add_argument("--max_top_y_diff", type=float, default=90.0,
                        help="Maximum allowed |TL.y - TR.y| in pixels. If exceeded, tighten top_pct iteratively.")

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
python pl_1_ransac_cld_split.py \
  --mask_input source_image/pro_mask_m_rm.png \
  --original_input source_image/pro_court.png \
  --out_root pl_1_ransac_spl_results \
  --open_ks 0 \
  --dilate_ks 3 \
  --enforce_vertical \
  --prefer_vertical_deg 25 \
  --horiz_kernel_ratio 0.25 \
  --horiz_iter 1 \
  --top_pct 2.0 \
  --bot_pct 98.0 \
  --max_top_y_diff 60



python pl_1_ransac_cld_split.py \
  --mask_input source_image/pro_mask_m_rm.png \
  --original_input source_image/pro_court.png \
  --out_root pl_1_ransac_spl_results

"""