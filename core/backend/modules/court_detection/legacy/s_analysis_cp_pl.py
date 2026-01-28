#!/usr/bin/env python3
"""
S Channel Analysis Tool for White Region Detection + Court Homography Pipeline

- 기존: HSV / YCbCr / LAB 기반으로 흰색(라인) 마스크 생성 및 시각화
- 추가: 생성된 이진 라인 마스크(우측 라인-온리 이미지)를 시작점으로
        사이드라인 기반 4점 추출 -> Homography 계산 -> (옵션) 전체 코트 템플릿을 투영/오버레이

주의:
- OpenCV 기본만 사용(추가 패키지 없음)
- thinning(스켈레톤)은 Zhang-Suen 구현(속도는 이미지 1장 기준 충분)
"""

import argparse
import datetime
import uuid
from pathlib import Path

import cv2
import numpy as np


# -----------------------------
# Utility I/O
# -----------------------------
def make_output_dir(root_dir: str) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    run_id = f"{timestamp}_{unique_id}"
    out_dir = Path(root_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def save_image(out_dir: Path, name: str, img: np.ndarray):
    path = out_dir / f"{name}.png"
    cv2.imwrite(str(path), img)
    print(f"[SAVED] {path}")


def to_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


# -----------------------------
# Thinning: Zhang-Suen
# -----------------------------
def zhang_suen_thinning(bin_img: np.ndarray, max_iter: int = 50) -> np.ndarray:
    """
    Input:  binary image in {0,255}
    Output: thinned binary image in {0,255}
    """
    img = (bin_img > 0).astype(np.uint8)
    h, w = img.shape[:2]

    def neighbors(x, y):
        # p2..p9
        p2 = img[x - 1, y]
        p3 = img[x - 1, y + 1]
        p4 = img[x, y + 1]
        p5 = img[x + 1, y + 1]
        p6 = img[x + 1, y]
        p7 = img[x + 1, y - 1]
        p8 = img[x, y - 1]
        p9 = img[x - 1, y - 1]
        return [p2, p3, p4, p5, p6, p7, p8, p9]

    def transitions(nei):
        # number of 0->1 transitions in p2..p9 circular
        n = 0
        for i in range(8):
            if nei[i] == 0 and nei[(i + 1) % 8] == 1:
                n += 1
        return n

    def sum_neighbors(nei):
        return sum(nei)

    changed = True
    it = 0
    while changed and it < max_iter:
        changed = False
        it += 1

        to_remove = []
        # Step 1
        for x in range(1, h - 1):
            for y in range(1, w - 1):
                if img[x, y] != 1:
                    continue
                nei = neighbors(x, y)
                n = sum_neighbors(nei)
                t = transitions(nei)
                p2, p3, p4, p5, p6, p7, p8, p9 = nei
                if (2 <= n <= 6 and t == 1 and
                    (p2 * p4 * p6) == 0 and
                    (p4 * p6 * p8) == 0):
                    to_remove.append((x, y))
        if to_remove:
            for x, y in to_remove:
                img[x, y] = 0
            changed = True

        to_remove = []
        # Step 2
        for x in range(1, h - 1):
            for y in range(1, w - 1):
                if img[x, y] != 1:
                    continue
                nei = neighbors(x, y)
                n = sum_neighbors(nei)
                t = transitions(nei)
                p2, p3, p4, p5, p6, p7, p8, p9 = nei
                if (2 <= n <= 6 and t == 1 and
                    (p2 * p4 * p8) == 0 and
                    (p2 * p6 * p8) == 0):
                    to_remove.append((x, y))
        if to_remove:
            for x, y in to_remove:
                img[x, y] = 0
            changed = True

    return (img * 255).astype(np.uint8)


# -----------------------------
# Mask preprocessing & filtering
# -----------------------------
def preprocess_line_mask(mask: np.ndarray, out_dir: Path, prefix: str = "P") -> np.ndarray:
    """
    - input mask {0,255}
    - remove small speckles
    - connect small gaps
    - connected component filter
    """
    m = (mask > 0).astype(np.uint8) * 255

    # Morphology
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    m_open = cv2.morphologyEx(m, cv2.MORPH_OPEN, k_open, iterations=1)
    m_close = cv2.morphologyEx(m_open, cv2.MORPH_CLOSE, k_close, iterations=1)

    save_image(out_dir, f"{prefix}_00_mask_raw", m)
    save_image(out_dir, f"{prefix}_01_mask_open", m_open)
    save_image(out_dir, f"{prefix}_02_mask_close", m_close)

    # Connected Components filter
    num, labels, stats, _ = cv2.connectedComponentsWithStats((m_close > 0).astype(np.uint8), connectivity=8)
    keep = np.zeros_like(m_close, dtype=np.uint8)

    h, w = m_close.shape[:2]
    img_area = h * w

    # Heuristic thresholds (tune if needed)
    min_area = max(80, int(img_area * 0.00002))  # very small removal
    for i in range(1, num):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue
        keep[labels == i] = 255

    save_image(out_dir, f"{prefix}_03_mask_cc_filtered", keep)
    return keep


# -----------------------------
# Line segment detection + clustering
# -----------------------------
def detect_line_segments(bin_img: np.ndarray):
    """
    Return segments: list of ((x1,y1,x2,y2), length, angle_rad, mid)
    """
    # OpenCV 4.x: use positional argument instead of keyword argument
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    # LSD expects 8-bit single channel; better with edges/skeleton.
    lines = lsd.detect(bin_img)[0]  # Nx1x4
    segments = []
    if lines is None:
        return segments

    for l in lines:
        x1, y1, x2, y2 = l[0]
        dx, dy = (x2 - x1), (y2 - y1)
        length = float(np.hypot(dx, dy))
        if length < 30:  # length filter (tune)
            continue
        angle = float(np.arctan2(dy, dx))  # [-pi, pi]
        # map to [0, pi)
        if angle < 0:
            angle += np.pi
        mid = ((x1 + x2) * 0.5, (y1 + y2) * 0.5)
        segments.append(((x1, y1, x2, y2), length, angle, mid))
    return segments


def cluster_segment_angles(segments, k=2):
    """
    cluster angles in [0, pi) using kmeans on unit circle doubled-angle trick:
    represent angle by (cos2a, sin2a) to handle antipodal equivalence.
    """
    if len(segments) < 10:
        return None, None

    feats = []
    for _, _, a, _ in segments:
        feats.append([np.cos(2 * a), np.sin(2 * a)])
    feats = np.float32(feats)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-4)
    _, labels, centers = cv2.kmeans(feats, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS)

    labels = labels.reshape(-1)
    return labels, centers


def draw_segments(img_bgr: np.ndarray, segments, labels=None, out_dir: Path = None, name: str = None):
    vis = img_bgr.copy()
    for i, (seg, length, angle, mid) in enumerate(segments):
        x1, y1, x2, y2 = map(int, seg)
        if labels is None:
            color = (0, 255, 0)
        else:
            color = (0, 0, 255) if int(labels[i]) == 0 else (255, 0, 0)
        cv2.line(vis, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
    if out_dir and name:
        save_image(out_dir, name, vis)
    return vis


# -----------------------------
# RANSAC line fitting + endpoints via projection
# -----------------------------
def fit_line_ransac(points_xy: np.ndarray, dist_th: float = 3.0, max_iter: int = 2000, min_inliers: int = 300):
    """
    Fit line in ax+by+c=0 from points using simple RANSAC.
    points_xy: Nx2 float
    Returns (a,b,c), inlier_mask (N,)
    """
    if points_xy.shape[0] < max(min_inliers, 100):
        return None, None

    pts = points_xy
    best_inliers = None
    best_model = None
    best_count = 0

    n = pts.shape[0]
    rng = np.random.default_rng(42)

    for _ in range(max_iter):
        i1, i2 = rng.integers(0, n, size=2)
        if i1 == i2:
            continue
        x1, y1 = pts[i1]
        x2, y2 = pts[i2]
        if abs(x2 - x1) + abs(y2 - y1) < 1e-6:
            continue

        # line through two points -> ax+by+c=0
        a = (y1 - y2)
        b = (x2 - x1)
        c = (x1 * y2 - x2 * y1)

        norm = np.hypot(a, b)
        if norm < 1e-9:
            continue
        a, b, c = a / norm, b / norm, c / norm

        # distances
        d = np.abs(a * pts[:, 0] + b * pts[:, 1] + c)
        inliers = d < dist_th
        count = int(inliers.sum())
        if count > best_count:
            best_count = count
            best_inliers = inliers
            best_model = (a, b, c)

    if best_model is None or best_count < min_inliers:
        return None, None

    # Refit using all inliers with cv2.fitLine for stability
    inlier_pts = pts[best_inliers].astype(np.float32)
    vx, vy, x0, y0 = cv2.fitLine(inlier_pts, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy, x0, y0 = float(vx), float(vy), float(x0), float(y0)

    # Convert to ax+by+c=0
    # Direction (vx,vy), normal (-vy, vx)
    a = -vy
    b = vx
    c = -(a * x0 + b * y0)
    norm = np.hypot(a, b)
    a, b, c = a / norm, b / norm, c / norm

    # recompute inliers w.r.t refined model
    d = np.abs(a * pts[:, 0] + b * pts[:, 1] + c)
    inliers = d < dist_th

    return (a, b, c), inliers


def line_direction_from_abc(a, b):
    """
    For ax + by + c = 0, a,b is normal.
    A direction vector is (b, -a).
    """
    d = np.array([b, -a], dtype=np.float32)
    dn = np.linalg.norm(d)
    if dn < 1e-9:
        return None
    return d / dn


def project_endpoints_from_inliers(model_abc, inlier_points_xy: np.ndarray):
    """
    Given line model and its inlier points, compute endpoints by projection extremes.
    Returns two endpoints (pt_min, pt_max) as float32.
    """
    a, b, c = model_abc
    d = line_direction_from_abc(a, b)  # unit direction
    if d is None:
        return None, None

    # pick a point on line as p0: closest point to origin along normal
    # For normalized a,b: point p0 = -c * [a,b]
    p0 = -c * np.array([a, b], dtype=np.float32)

    # projection t = d dot (x - p0)
    X = inlier_points_xy.astype(np.float32)
    t = (X - p0) @ d  # (N,)
    tmin, tmax = float(np.min(t)), float(np.max(t))

    p_min = p0 + tmin * d
    p_max = p0 + tmax * d
    return p_min, p_max


def draw_line_abc(img_bgr: np.ndarray, model_abc, color=(0, 255, 255), thickness=2):
    a, b, c = model_abc
    h, w = img_bgr.shape[:2]

    # intersect with image borders to draw segment
    pts = []
    # x=0 -> by + c = 0 => y = -c/b
    if abs(b) > 1e-9:
        y = -c / b
        if 0 <= y < h:
            pts.append((0, int(round(y))))
    # x=w-1
    if abs(b) > 1e-9:
        y = -(a * (w - 1) + c) / b
        if 0 <= y < h:
            pts.append((w - 1, int(round(y))))
    # y=0 -> ax + c = 0 => x = -c/a
    if abs(a) > 1e-9:
        x = -c / a
        if 0 <= x < w:
            pts.append((int(round(x)), 0))
    # y=h-1
    if abs(a) > 1e-9:
        x = -(b * (h - 1) + c) / a
        if 0 <= x < w:
            pts.append((int(round(x)), h - 1))

    if len(pts) >= 2:
        p1 = pts[0]
        p2 = pts[1]
        cv2.line(img_bgr, p1, p2, color, thickness, cv2.LINE_AA)

    return img_bgr


# -----------------------------
# Court template generation & warping
# -----------------------------
def create_badminton_court_template(dst_w: int, dst_h: int) -> np.ndarray:
    """
    Create a simple doubles badminton court line template in the canonical plane.
    White background, black lines.
    """
    img = np.ones((dst_h, dst_w, 3), dtype=np.uint8) * 255

    # Court real dims (meters): doubles width 6.10, length 13.40
    # We'll map to pixels with margins.
    margin = int(0.05 * min(dst_w, dst_h))
    x0, y0 = margin, margin
    x1, y1 = dst_w - margin, dst_h - margin

    # Outer boundary
    cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 0), 3)

    # Key lines (approx ratios)
    # Center line (longitudinal center)
    cx = (x0 + x1) // 2
    cv2.line(img, (cx, y0), (cx, y1), (0, 0, 0), 2)

    # Net line at half length
    ny = (y0 + y1) // 2
    cv2.line(img, (x0, ny), (x1, ny), (0, 0, 0), 2)

    # Service lines (doubles)
    # Short service line: 1.98m from net on both sides
    # Half-court length: 6.70m. ratio = 1.98 / 6.70
    r_short = 1.98 / 6.70
    y_short_top = int(round(ny - r_short * (ny - y0)))
    y_short_bot = int(round(ny + r_short * (y1 - ny)))
    cv2.line(img, (x0, y_short_top), (x1, y_short_top), (0, 0, 0), 2)
    cv2.line(img, (x0, y_short_bot), (x1, y_short_bot), (0, 0, 0), 2)

    # Long service line for doubles: 0.76m from baseline
    # ratio = 0.76 / 6.70
    r_long = 0.76 / 6.70
    y_long_top = int(round(y0 + r_long * (ny - y0)))
    y_long_bot = int(round(y1 - r_long * (y1 - ny)))
    cv2.line(img, (x0, y_long_top), (x1, y_long_top), (0, 0, 0), 2)
    cv2.line(img, (x0, y_long_bot), (x1, y_long_bot), (0, 0, 0), 2)

    # Singles side lines (optional): singles width 5.18m inside doubles by 0.46m each side
    # ratio offset = 0.46 / 6.10
    r_side = 0.46 / 6.10
    x_s_left = int(round(x0 + r_side * (x1 - x0)))
    x_s_right = int(round(x1 - r_side * (x1 - x0)))
    cv2.line(img, (x_s_left, y0), (x_s_left, y1), (0, 0, 0), 2)
    cv2.line(img, (x_s_right, y0), (x_s_right, y1), (0, 0, 0), 2)

    return img


def overlay_template_on_original(bgr_img: np.ndarray, H: np.ndarray, template: np.ndarray, alpha: float = 0.55) -> np.ndarray:
    """
    Warp template (canonical plane) back onto original image and overlay.
    """
    h, w = bgr_img.shape[:2]
    H_inv = np.linalg.inv(H)

    warped = cv2.warpPerspective(template, H_inv, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    # Use template lines as mask: black pixels
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    mask = gray < 200

    out = bgr_img.copy()
    out[mask] = (alpha * out[mask] + (1 - alpha) * warped[mask]).astype(np.uint8)
    return out


# -----------------------------
# Core pipeline: from line mask -> 4 points -> Homography
# -----------------------------
def estimate_court_homography_from_line_mask(
    bgr_img: np.ndarray,
    line_mask_255: np.ndarray,
    out_dir: Path,
    prefix: str = "HOMO",
):
    """
    Returns:
      - success: bool
      - points_src: dict with keys: lb, rb, rt, lt (float32)
      - H: homography mapping original->canonical
      - warped: warped original image
      - debug images saved
    """
    h, w = line_mask_255.shape[:2]

    # 1) preprocess
    clean = preprocess_line_mask(line_mask_255, out_dir, prefix=f"{prefix}_A")

    # 2) thinning/skeleton
    skel = zhang_suen_thinning(clean, max_iter=60)
    save_image(out_dir, f"{prefix}_B_00_skeleton", skel)

    # 3) LSD segments
    segments = detect_line_segments(skel)
    seg_vis = draw_segments(to_bgr(skel), segments, labels=None, out_dir=out_dir, name=f"{prefix}_C_00_segments_all")
    if len(segments) < 10:
        print("[WARN] Not enough segments for clustering. Homography skipped.")
        return False, None, None, None, None

    # 4) angle clustering k=2
    labels, _ = cluster_segment_angles(segments, k=2)
    if labels is None:
        print("[WARN] Clustering failed. Homography skipped.")
        return False, None, None, None, None

    draw_segments(to_bgr(skel), segments, labels=labels, out_dir=out_dir, name=f"{prefix}_C_01_segments_clustered")

    # 5) choose side-line cluster (score both)
    # score: (total length of segments near left+right extremes at y*=0.85H)
    y_star = int(0.85 * h)

    def x_at_y(seg, yq):
        x1, y1, x2, y2 = seg
        if abs(y2 - y1) < 1e-6:
            return None
        t = (yq - y1) / (y2 - y1)
        x = x1 + t * (x2 - x1)
        return float(x)

    cluster_scores = []
    for cid in [0, 1]:
        xs = []
        total_len = 0.0
        for i, (seg, length, angle, mid) in enumerate(segments):
            if int(labels[i]) != cid:
                continue
            x = x_at_y(seg, y_star)
            if x is None:
                continue
            if 0 <= x < w:
                xs.append(x)
                total_len += length
        if len(xs) < 4:
            cluster_scores.append(-1e9)
            continue
        xs = np.array(xs, dtype=np.float32)
        spread = float(np.percentile(xs, 90) - np.percentile(xs, 10))
        # want large spread (left+right existence) and large total_len
        cluster_scores.append(0.7 * spread + 0.3 * total_len)

    side_cluster = int(np.argmax(cluster_scores))
    print(f"[INFO] side_cluster selected = {side_cluster}, scores={cluster_scores}")

    # 6) collect candidate points near side cluster segments:
    #    We gate by segment angle cluster first, then RANSAC on pixels.
    ys, xs = np.where(skel > 0)
    all_pts = np.stack([xs, ys], axis=1).astype(np.float32)  # Nx2

    # For splitting left/right: use x-intercept at y* estimated from segments in chosen cluster
    xints = []
    for i, (seg, length, angle, mid) in enumerate(segments):
        if int(labels[i]) != side_cluster:
            continue
        x = x_at_y(seg, y_star)
        if x is None:
            continue
        if 0 <= x < w:
            xints.append(x)
    if len(xints) < 6:
        print("[WARN] Not enough side-cluster intercepts. Homography skipped.")
        return False, None, None, None, None

    xints = np.array(xints, dtype=np.float32)
    x_left_seed = float(np.percentile(xints, 15))
    x_right_seed = float(np.percentile(xints, 85))

    # Left / Right seed split by x coordinate
    left_pts = all_pts[all_pts[:, 0] < (x_left_seed + x_right_seed) * 0.5]
    right_pts = all_pts[all_pts[:, 0] >= (x_left_seed + x_right_seed) * 0.5]

    # RANSAC fit each side line
    # thresholds tuned for skeleton (thin). If your mask is thicker, dist_th up.
    left_model, left_inliers = fit_line_ransac(left_pts, dist_th=3.0, max_iter=2500, min_inliers=200)
    right_model, right_inliers = fit_line_ransac(right_pts, dist_th=3.0, max_iter=2500, min_inliers=200)

    if left_model is None or right_model is None:
        print("[WARN] RANSAC failed to fit both side lines. Homography skipped.")
        return False, None, None, None, None

    # 7) endpoints via projection extremes
    l_inlier_pts = left_pts[left_inliers]
    r_inlier_pts = right_pts[right_inliers]
    L_top, L_bot = project_endpoints_from_inliers(left_model, l_inlier_pts)
    R_top, R_bot = project_endpoints_from_inliers(right_model, r_inlier_pts)

    if L_top is None or R_top is None:
        print("[WARN] Endpoint projection failed.")
        return False, None, None, None, None

    # enforce ordering by y (top smaller y)
    if L_top[1] > L_bot[1]:
        L_top, L_bot = L_bot, L_top
    if R_top[1] > R_bot[1]:
        R_top, R_bot = R_bot, R_top

    pts = {
        "lb": L_bot.astype(np.float32),
        "rb": R_bot.astype(np.float32),
        "rt": R_top.astype(np.float32),
        "lt": L_top.astype(np.float32),
    }

    # 8) visualize fitted lines + endpoints + quad
    vis = bgr_img.copy()
    draw_line_abc(vis, left_model, color=(0, 255, 255), thickness=3)
    draw_line_abc(vis, right_model, color=(255, 255, 0), thickness=3)

    def draw_point(img, p, color, r=6):
        cv2.circle(img, (int(round(p[0])), int(round(p[1]))), r, color, -1, cv2.LINE_AA)

    draw_point(vis, pts["lt"], (0, 0, 255))
    draw_point(vis, pts["lb"], (0, 0, 255))
    draw_point(vis, pts["rt"], (0, 255, 0))
    draw_point(vis, pts["rb"], (0, 255, 0))

    quad = np.array([pts["lt"], pts["rt"], pts["rb"], pts["lb"]], dtype=np.int32)
    cv2.polylines(vis, [quad], isClosed=True, color=(255, 0, 255), thickness=3, lineType=cv2.LINE_AA)
    save_image(out_dir, f"{prefix}_D_00_lines_endpoints_quad", vis)

    # 9) build canonical destination rectangle with badminton aspect ratio
    # ratio length/width = 13.4 / 6.1
    dst_w = 700
    dst_h = int(round(dst_w * (13.4 / 6.1)))
    dst = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype=np.float32)

    src = np.array([pts["lt"], pts["rt"], pts["rb"], pts["lb"]], dtype=np.float32)

    H = cv2.getPerspectiveTransform(src, dst)

    warped = cv2.warpPerspective(bgr_img, H, (dst_w, dst_h), flags=cv2.INTER_LINEAR)
    save_image(out_dir, f"{prefix}_E_00_warped_original", warped)

    warped_mask = cv2.warpPerspective(line_mask_255, H, (dst_w, dst_h), flags=cv2.INTER_NEAREST)
    save_image(out_dir, f"{prefix}_E_01_warped_line_mask", warped_mask)

    # 10) draw full court template in canonical plane and overlay back
    template = create_badminton_court_template(dst_w, dst_h)
    save_image(out_dir, f"{prefix}_F_00_court_template_canonical", template)

    overlay = overlay_template_on_original(bgr_img, H, template, alpha=0.65)
    save_image(out_dir, f"{prefix}_F_01_template_overlay_on_original", overlay)

    # also show warped with template for sanity
    warped_overlay = warped.copy()
    # overlay template lines directly in canonical
    gray_t = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    m = gray_t < 200
    warped_overlay[m] = (0.6 * warped_overlay[m] + 0.4 * template[m]).astype(np.uint8)
    save_image(out_dir, f"{prefix}_F_02_template_overlay_on_warped", warped_overlay)

    return True, pts, H, warped, overlay


# -----------------------------
# Original analyses (kept) + ensemble hook
# -----------------------------
def create_histogram_image(channel: np.ndarray, title: str, thresholds: list) -> np.ndarray:
    hist_height = 400
    hist_width = 512

    hist = cv2.calcHist([channel], [0], None, [256], [0, 256])
    hist_norm = hist / max(hist.max(), 1e-6) * (hist_height - 50)

    hist_img = np.ones((hist_height, hist_width, 3), dtype=np.uint8) * 255

    bin_width = hist_width / 256
    for i in range(256):
        x = int(i * bin_width)
        y = int(hist_norm[i])
        cv2.line(hist_img, (x, hist_height - 30), (x, hist_height - 30 - y), (100, 100, 100), 1)

    for th in thresholds:
        x = int(th * bin_width)
        cv2.line(hist_img, (x, 0), (x, hist_height - 30), (0, 0, 255), 2)
        cv2.putText(hist_img, str(th), (x - 10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    cv2.putText(hist_img, title, (10, hist_height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(hist_img, "0", (5, hist_height - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.putText(hist_img, "255", (hist_width - 30, hist_height - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    return hist_img


def analyze_s_channel(bgr_img: np.ndarray, out_dir: Path):
    h, w = bgr_img.shape[:2]

    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = cv2.split(hsv)

    save_image(out_dir, "00_original", bgr_img)
    save_image(out_dir, "01_h_channel", h_ch)
    save_image(out_dir, "01_s_channel", s_ch)
    save_image(out_dir, "01_v_channel", v_ch)

    s_min, s_max = int(s_ch.min()), int(s_ch.max())
    s_mean, s_std = float(s_ch.mean()), float(s_ch.std())

    print(f"\n[S Channel Statistics]")
    print(f"  Min: {s_min}, Max: {s_max}")
    print(f"  Mean: {s_mean:.2f}, Std: {s_std:.2f}")

    stats_file = out_dir / "s_channel_stats.txt"
    with open(stats_file, "w") as f:
        f.write("S Channel Statistics\n====================\n")
        f.write(f"Min: {s_min}\nMax: {s_max}\nMean: {s_mean:.2f}\nStd: {s_std:.2f}\n")
    print(f"[SAVED] {stats_file}")

    s_thresholds = [30, 50, 70, 90, 110, 130]

    for s_th in s_thresholds:
        mask = (s_ch < s_th).astype(np.uint8) * 255

        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]

        h_concat = np.hstack([bgr_img, result])

        text = f"S < {s_th}"
        cv2.putText(h_concat, text, (w + 20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3, cv2.LINE_AA)

        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)

        save_image(out_dir, f"02_s_threshold_{s_th:03d}", h_concat)
        print(f"  S < {s_th}: {detected_ratio:.2f}% detected")

    print(f"\n[Combined S & V Channel Analysis]")
    combined_configs = [
        {"s_max": 90, "v_min": 150, "name": "s90_v150"},
        {"s_max": 70, "v_min": 170, "name": "s70_v170"},
        {"s_max": 50, "v_min": 180, "name": "s50_v180"},
    ]

    for cfg in combined_configs:
        s_max = cfg["s_max"]
        v_min = cfg["v_min"]
        name = cfg["name"]

        mask = ((s_ch < s_max) & (v_ch > v_min)).astype(np.uint8) * 255
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]

        h_concat = np.hstack([bgr_img, result])

        text = f"S<{s_max} & V>{v_min}"
        cv2.putText(h_concat, text, (w + 20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3, cv2.LINE_AA)

        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

        save_image(out_dir, f"03_combined_{name}", h_concat)
        print(f"  S<{s_max} & V>{v_min}: {detected_ratio:.2f}% detected")

    hist_img = create_histogram_image(s_ch, "S Channel Histogram", s_thresholds)
    save_image(out_dir, "04_s_histogram", hist_img)


def analyze_ycbcr_channel(bgr_img: np.ndarray, out_dir: Path):
    h, w = bgr_img.shape[:2]
    print(f"\n[YCbCr Y Channel Analysis]")

    ycbcr = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
    y_ch, cr_ch, cb_ch = cv2.split(ycbcr)

    save_image(out_dir, "05_y_channel", y_ch)
    save_image(out_dir, "05_cr_channel", cr_ch)
    save_image(out_dir, "05_cb_channel", cb_ch)

    y_min, y_max = int(y_ch.min()), int(y_ch.max())
    y_mean, y_std = float(y_ch.mean()), float(y_ch.std())
    print(f"  Min: {y_min}, Max: {y_max}")
    print(f"  Mean: {y_mean:.2f}, Std: {y_std:.2f}")

    stats_file = out_dir / "y_channel_stats.txt"
    with open(stats_file, "w") as f:
        f.write("Y Channel Statistics\n====================\n")
        f.write(f"Min: {y_min}\nMax: {y_max}\nMean: {y_mean:.2f}\nStd: {y_std:.2f}\n")
    print(f"[SAVED] {stats_file}")

    y_thresholds = [180, 190, 200, 210, 220, 230]
    for y_th in y_thresholds:
        mask = (y_ch > y_th).astype(np.uint8) * 255
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]

        h_concat = np.hstack([bgr_img, result])

        text = f"Y > {y_th}"
        cv2.putText(h_concat, text, (w + 20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3, cv2.LINE_AA)

        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)

        save_image(out_dir, f"06_y_threshold_{y_th:03d}", h_concat)
        print(f"  Y > {y_th}: {detected_ratio:.2f}% detected")

    hist_img = create_histogram_image(y_ch, "Y Channel Histogram", y_thresholds)
    save_image(out_dir, "07_y_histogram", hist_img)


def analyze_lab_channel(bgr_img: np.ndarray, out_dir: Path):
    h, w = bgr_img.shape[:2]
    print(f"\n[LAB L Channel Analysis]")

    lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)

    save_image(out_dir, "08_l_channel", l_ch)
    save_image(out_dir, "08_a_channel", a_ch)
    save_image(out_dir, "08_b_channel", b_ch)

    l_min, l_max = int(l_ch.min()), int(l_ch.max())
    l_mean, l_std = float(l_ch.mean()), float(l_ch.std())
    print(f"  Min: {l_min}, Max: {l_max}")
    print(f"  Mean: {l_mean:.2f}, Std: {l_std:.2f}")

    stats_file = out_dir / "l_channel_stats.txt"
    with open(stats_file, "w") as f:
        f.write("L Channel Statistics\n====================\n")
        f.write(f"Min: {l_min}\nMax: {l_max}\nMean: {l_mean:.2f}\nStd: {l_std:.2f}\n")
    print(f"[SAVED] {stats_file}")

    l_thresholds = [180, 190, 200, 210, 220, 230]
    for l_th in l_thresholds:
        mask = (l_ch > l_th).astype(np.uint8) * 255
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]

        h_concat = np.hstack([bgr_img, result])

        text = f"L > {l_th}"
        cv2.putText(h_concat, text, (w + 20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (180, 105, 255), 3, cv2.LINE_AA)

        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 105, 255), 2, cv2.LINE_AA)

        save_image(out_dir, f"09_l_threshold_{l_th:03d}", h_concat)
        print(f"  L > {l_th}: {detected_ratio:.2f}% detected")

    hist_img = create_histogram_image(l_ch, "L Channel Histogram", l_thresholds)
    save_image(out_dir, "10_l_histogram", hist_img)


def analyze_ensemble(bgr_img: np.ndarray, out_dir: Path):
    """
    앙상블 마스크 생성 + (추가) Homography 파이프라인 수행
    """
    h, w = bgr_img.shape[:2]
    print(f"\n[Ensemble Analysis - Multi Color Space]")

    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    ycbcr = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
    lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)

    _, s_ch, v_ch = cv2.split(hsv)
    y_ch, _, _ = cv2.split(ycbcr)
    l_ch, _, _ = cv2.split(lab)

    ensemble_configs = [
        {
            "name": "conservative",
            "desc": "HSV AND YCbCr AND LAB",
            "s_max": 90, "v_min": 150,
            "y_min": 200,
            "l_min": 200,
            "operation": "and",
        },
        {
            "name": "moderate",
            "desc": "At least 2 of 3",
            "s_max": 90, "v_min": 150,
            "y_min": 200,
            "l_min": 200,
            "operation": "voting",
        },
        {
            "name": "aggressive",
            "desc": "HSV OR YCbCr OR LAB",
            "s_max": 90, "v_min": 150,
            "y_min": 200,
            "l_min": 200,
            "operation": "or",
        },
    ]

    # 1) save ensemble masks + preview
    masks = {}
    for cfg in ensemble_configs:
        mask_hsv = ((s_ch < cfg["s_max"]) & (v_ch > cfg["v_min"])).astype(np.uint8)
        mask_ycbcr = (y_ch > cfg["y_min"]).astype(np.uint8)
        mask_lab = (l_ch > cfg["l_min"]).astype(np.uint8)

        if cfg["operation"] == "and":
            mask_final = (mask_hsv & mask_ycbcr & mask_lab) * 255
        elif cfg["operation"] == "voting":
            mask_final = ((mask_hsv.astype(int) + mask_ycbcr.astype(int) + mask_lab.astype(int)) >= 2).astype(np.uint8) * 255
        else:
            mask_final = (mask_hsv | mask_ycbcr | mask_lab) * 255

        masks[cfg["name"]] = mask_final

        # visualization (existing style)
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask_final > 0] = [0, 0, 0]

        h_concat = np.hstack([bgr_img, result])

        text = f"Ensemble: {cfg['name']}"
        cv2.putText(h_concat, text, (w + 20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 128, 0), 3, cv2.LINE_AA)

        detected_ratio = (mask_final > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 128, 0), 2, cv2.LINE_AA)

        desc_text = cfg["desc"]
        cv2.putText(h_concat, desc_text, (w + 20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 2, cv2.LINE_AA)

        save_image(out_dir, f"11_ensemble_{cfg['name']}", h_concat)
        save_image(out_dir, f"11_ensemble_{cfg['name']}_mask_only", mask_final)
        print(f"  {cfg['name']}: {detected_ratio:.2f}% detected")

    print(f"\n[Homography Pipeline] start with one selected ensemble mask")

    # 2) 선택: conservative 마스크를 기본 입력으로 사용
    #    (과검출을 줄이고 직선 구조를 안정화하기 위함)
    selected_name = "conservative"
    line_mask = masks[selected_name]

    ok, pts, H, warped, overlay = estimate_court_homography_from_line_mask(
        bgr_img=bgr_img,
        line_mask_255=line_mask,
        out_dir=out_dir,
        prefix=f"HOMO_{selected_name}",
    )

    if ok:
        print("\n[Homography Result - 4 Points]")
        for k in ["lt", "rt", "rb", "lb"]:
            p = pts[k]
            print(f"  {k}: ({p[0]:.2f}, {p[1]:.2f})")
        # Save points to text
        pfile = out_dir / f"homography_points_{selected_name}.txt"
        with open(pfile, "w") as f:
            for k in ["lt", "rt", "rb", "lb"]:
                p = pts[k]
                f.write(f"{k}: {p[0]:.6f}, {p[1]:.6f}\n")
        print(f"[SAVED] {pfile}")
    else:
        print("[WARN] Homography pipeline failed. Check saved debug images and tune thresholds.")


def main():
    parser = argparse.ArgumentParser(description="S Channel Analysis Tool for White Region Detection + Court Homography")
    parser.add_argument("--input", required=True, help="Path to input image file")
    parser.add_argument("--out_root", required=True, help="Root directory for output results")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {args.input}")

    bgr_img = cv2.imread(str(input_path))
    if bgr_img is None:
        raise ValueError(f"Failed to read image: {args.input}")

    print(f"[INFO] Input image: {input_path}")
    print(f"[INFO] Image size: {bgr_img.shape[1]}x{bgr_img.shape[0]}")

    out_dir = make_output_dir(args.out_root)
    print(f"[INFO] Output directory: {out_dir}")

    analyze_s_channel(bgr_img, out_dir)
    analyze_ycbcr_channel(bgr_img, out_dir)
    analyze_lab_channel(bgr_img, out_dir)
    analyze_ensemble(bgr_img, out_dir)

    print(f"\n[DONE] All results saved to: {out_dir}")


if __name__ == "__main__":
    main()


"""
Example:
python s_analysis_cp_pl.py --input source_image/pro_court.png --out_root s_analysis_results
python s_analysis_cp_pl.py --input source_image/amatuer_court.jpg --out_root s_analysis_results
python s_analysis_cp_pl.py --input source_image/pro_court_highangle.png --out_root s_analysis_results

python s_analysis_cp_pl.py --input source_image/pro_court_m_rm.jpg --out_root s_analysis_results



# 2
python s_analysis_cp_pl.py --input source_image/pro_court_highangle.png --out_root s_analysis_results

# 3
python s_analysis_cp_pl.py --input source_image/pro_court_topview.png --out_root s_analysis_results

# 4
python s_analysis_cp_pl.py --input source_image/amatuer_court.jpg --out_root s_analysis_results



"""
