#!/usr/bin/env python3
"""
Badminton Court 4-Point Estimator (Side-lines only)

Goal
- 입력: A_00 마스크(코트 라인 마스크) 1장
- 출력: TL / TR / BR / BL 4점 (오직 "최외곽" 좌/우 사이드라인 2개로부터 끝점 추정)
- 제약: 상대 코트의 수평 라인(베이스/서비스) 검출이 약해도 동작해야 함
- 방식: (강한 정제/스켈레톤 없이) 2-라인 RANSAC + 끝점(투영 극값) + 상단 보정(분위수/쌍제약)

저장
- 단계별 시각화 이미지를 다수 저장하여, 사용자가 순차적으로 확인 가능

Usage
python court_4pt_from_mask.py \
  --mask_input path/to/HOMO_conservative_A_00_mask_raw.png \
  --out_root results_dir

(선택) 원본 프레임을 함께 오버레이하고 싶다면
python court_4pt_from_mask.py \
  --mask_input ...png \
  --original_input ...png \
  --out_root results_dir
"""

import argparse
import datetime
import uuid
from pathlib import Path

import cv2
import numpy as np


# -----------------------------
# I/O Utilities
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
# Minimal preprocessing (NO aggressive cleanup)
# -----------------------------
def normalize_mask_to_255(mask_in: np.ndarray) -> np.ndarray:
    """
    입력 마스크가 0/255가 아닐 수도 있으므로, 일단 threshold로 이진화.
    """
    if mask_in.ndim == 3:
        mask = cv2.cvtColor(mask_in, cv2.COLOR_BGR2GRAY)
    else:
        mask = mask_in.copy()

    # Otsu + fallback
    _, bin1 = cv2.threshold(mask, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 만약 화면이 거의 흰색/검정색으로 치우쳐 Otsu가 애매하면 고정 임계도 한번 적용
    if (bin1 > 0).mean() < 0.0005:
        _, bin1 = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
    elif (bin1 > 0).mean() > 0.95:
        _, bin1 = cv2.threshold(mask, 50, 255, cv2.THRESH_BINARY)

    return bin1


def build_edge_for_line_support(mask255: np.ndarray, out_dir: Path, prefix: str, open_ks: int, dil_ks: int):
    """
    - 스켈레톤/강한 CC 필터 금지
    - 아주 약한 open / dilation은 옵션
    - edge는 morphological gradient 기반
    """
    m = mask255.copy()

    # weak open (speckle 조금만)
    if open_ks > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_ks, open_ks))
        m_open = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=1)
    else:
        m_open = m

    # weak dilation (라인 지지 픽셀 조금 확장)
    if dil_ks > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dil_ks, dil_ks))
        m_dil = cv2.dilate(m_open, k, iterations=1)
    else:
        m_dil = m_open

    # morphological gradient -> edge 강조
    kgrad = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edge = cv2.morphologyEx(m_dil, cv2.MORPH_GRADIENT, kgrad)

    save_image(out_dir, f"{prefix}_00_mask_norm", m)
    save_image(out_dir, f"{prefix}_01_mask_weak_open", m_open)
    save_image(out_dir, f"{prefix}_02_mask_weak_dilate", m_dil)
    save_image(out_dir, f"{prefix}_03_edge_morph_gradient", edge)

    return m_open, m_dil, edge


# -----------------------------
# Line model & RANSAC
# -----------------------------
def line_from_two_points(p1: np.ndarray, p2: np.ndarray):
    """
    Return line param:
      - p0: point on line (float32)
      - d: unit direction vector (float32)
      - n: unit normal vector (float32)
    """
    v = p2 - p1
    norm = float(np.linalg.norm(v))
    if norm < 1e-6:
        return None
    d = (v / norm).astype(np.float32)
    n = np.array([-d[1], d[0]], dtype=np.float32)
    p0 = p1.astype(np.float32)
    return p0, d, n


def point_line_dist(points: np.ndarray, p0: np.ndarray, n: np.ndarray) -> np.ndarray:
    """
    distance = |(p - p0) dot n|
    points Nx2
    """
    return np.abs((points - p0) @ n)


def angle_deg_from_dir(d: np.ndarray) -> float:
    """
    Direction angle in degrees in [0, 180)
    """
    ang = np.degrees(np.arctan2(float(d[1]), float(d[0])))
    if ang < 0:
        ang += 180.0
    return ang


def ransac_single_line(
    points: np.ndarray,
    dist_th: float,
    max_iter: int,
    min_inliers: int,
    forbid_horizontal_deg: float,
):
    """
    Fit a single dominant line using RANSAC.
    - points: Nx2 float32
    - forbid_horizontal_deg: 수평에 너무 가까운 라인 배제(예: 15도)
    Return:
      p0,d,n,inlier_mask or None
    """
    n_pts = points.shape[0]
    if n_pts < max(200, min_inliers):
        return None

    rng = np.random.default_rng(42)
    best = None
    best_cnt = 0

    # Precompute indices for speed
    for _ in range(max_iter):
        i1, i2 = rng.integers(0, n_pts, size=2)
        if i1 == i2:
            continue
        p1 = points[i1]
        p2 = points[i2]
        model = line_from_two_points(p1, p2)
        if model is None:
            continue
        p0, d, n = model

        # forbid near-horizontal lines
        ang = angle_deg_from_dir(d)
        # horizontal ~ 0 or 180
        if ang < forbid_horizontal_deg or ang > (180.0 - forbid_horizontal_deg):
            continue

        dist = point_line_dist(points, p0, n)
        inliers = dist < dist_th
        cnt = int(inliers.sum())
        if cnt > best_cnt:
            best_cnt = cnt
            best = (p0, d, n, inliers)

    if best is None or best_cnt < min_inliers:
        return None

    # Refine using cv2.fitLine on inliers (more stable)
    p0, d, n, inliers = best
    inlier_pts = points[inliers].astype(np.float32)

    # cv2.fitLine expects Nx1x2 or Nx2; give Nx2
    vx, vy, x0, y0 = cv2.fitLine(inlier_pts, cv2.DIST_L2, 0, 0.01, 0.01)
    d_ref = np.array([float(vx), float(vy)], dtype=np.float32)
    dn = float(np.linalg.norm(d_ref))
    if dn < 1e-6:
        return None
    d_ref /= dn
    n_ref = np.array([-d_ref[1], d_ref[0]], dtype=np.float32)
    p0_ref = np.array([float(x0), float(y0)], dtype=np.float32)

    # recompute inliers w.r.t refined model
    dist2 = point_line_dist(points, p0_ref, n_ref)
    inliers2 = dist2 < dist_th

    if int(inliers2.sum()) < min_inliers:
        # fallback to original best
        return p0, d, n, inliers

    return p0_ref, d_ref, n_ref, inliers2


def x_at_y(p0: np.ndarray, d: np.ndarray, y_query: float):
    """
    Parametric line: p = p0 + t*d
    Solve y_query = p0.y + t*d.y -> t = (y_query - p0.y)/d.y
    """
    if abs(float(d[1])) < 1e-6:
        return None
    t = (y_query - float(p0[1])) / float(d[1])
    x = float(p0[0]) + t * float(d[0])
    return x


def project_endpoints(points: np.ndarray, p0: np.ndarray, d: np.ndarray):
    """
    Endpoints from projection extremes along d:
      t = (p - p0) dot d
      p_end = p0 + t_end*d
    """
    t = (points - p0) @ d
    tmin = float(np.min(t))
    tmax = float(np.max(t))
    p_min = p0 + tmin * d
    p_max = p0 + tmax * d
    return p_min.astype(np.float32), p_max.astype(np.float32)


# -----------------------------
# Endpoint selection with top-weakness compensation
# -----------------------------
def robust_side_endpoints(
    inlier_pts: np.ndarray,
    p0: np.ndarray,
    d: np.ndarray,
    top_pct: float,
    bot_pct: float,
    min_subset: int = 60,
):
    """
    - Bottom endpoint: use bottom y-quantile subset (strong)
    - Top endpoint: use top y-quantile subset (weak / sparse)
    """
    ys = inlier_pts[:, 1]
    # Smaller y = upper
    y_top_th = np.percentile(ys, top_pct)
    y_bot_th = np.percentile(ys, bot_pct)

    top_subset = inlier_pts[ys <= y_top_th + 1.0]
    bot_subset = inlier_pts[ys >= y_bot_th - 1.0]

    # Fallback if too few
    if top_subset.shape[0] < min_subset:
        top_subset = inlier_pts
    if bot_subset.shape[0] < min_subset:
        bot_subset = inlier_pts

    # For top: choose endpoint among top_subset by projection extreme (toward top)
    # We can simply take projection extremes, then pick the one with smaller y as top.
    t_end1, t_end2 = project_endpoints(top_subset, p0, d)
    top_pt = t_end1 if t_end1[1] < t_end2[1] else t_end2

    # For bottom: projection extremes then pick bigger y
    b_end1, b_end2 = project_endpoints(bot_subset, p0, d)
    bot_pt = b_end1 if b_end1[1] > b_end2[1] else b_end2

    return top_pt, bot_pt, y_top_th, y_bot_th


def enforce_paired_top_constraint(
    L_inliers: np.ndarray,
    R_inliers: np.ndarray,
    L_p0: np.ndarray,
    L_d: np.ndarray,
    R_p0: np.ndarray,
    R_d: np.ndarray,
    top_pct_init: float,
    bot_pct: float,
    max_top_y_diff: float,
):
    """
    If TL/TR y difference is too large, tighten the top selection by using a smaller common y-threshold.
    This does NOT rely on any horizontal lines.
    """
    top_pct = float(top_pct_init)

    # Base endpoints
    TL, BL, yL_top_th, yL_bot_th = None, None, None, None
    TR, BR, yR_top_th, yR_bot_th = None, None, None, None

    for _ in range(6):
        TL, BL, yL_top_th, _ = robust_side_endpoints(L_inliers, L_p0, L_d, top_pct, bot_pct)
        TR, BR, yR_top_th, _ = robust_side_endpoints(R_inliers, R_p0, R_d, top_pct, bot_pct)

        dy = abs(float(TL[1]) - float(TR[1]))
        if dy <= max_top_y_diff:
            return TL, TR, BL, BR, top_pct, dy

        # tighten: reduce percentile (use more "uppermost" points)
        top_pct *= 0.6
        if top_pct < 0.2:
            break

    # Return the last attempt even if still large
    dy = abs(float(TL[1]) - float(TR[1]))
    return TL, TR, BL, BR, top_pct, dy


# -----------------------------
# Visualization
# -----------------------------
def subset_by_top_percentile(inlier_pts: np.ndarray, top_pct: float, pad: float = 1.0):
    """
    inlier_pts 중에서 '상단' 픽셀만 추출 (y가 작은 쪽)
    - top_pct: 예) 3.0 => 상단 3% 분위수
    - pad: threshold 주변 여유
    """
    ys = inlier_pts[:, 1]
    y_th = np.percentile(ys, top_pct)
    subset = inlier_pts[ys <= (y_th + pad)]
    return subset, float(y_th)


def draw_segment(img_bgr: np.ndarray, pA: np.ndarray, pB: np.ndarray, color, thickness=3):
    x1, y1 = int(round(float(pA[0]))), int(round(float(pA[1])))
    x2, y2 = int(round(float(pB[0]))), int(round(float(pB[1])))
    cv2.line(img_bgr, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
    return img_bgr


def draw_line_on_image(img_bgr: np.ndarray, p0: np.ndarray, d: np.ndarray, color, thickness=2):
    """
    Draw a line by intersecting with image borders
    """
    h, w = img_bgr.shape[:2]
    # two points far apart
    t0 = -2000.0
    t1 = 2000.0
    pA = p0 + t0 * d
    pB = p0 + t1 * d
    x1, y1 = int(round(float(pA[0]))), int(round(float(pA[1])))
    x2, y2 = int(round(float(pB[0]))), int(round(float(pB[1])))
    cv2.line(img_bgr, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
    return img_bgr


def draw_point(img_bgr: np.ndarray, p: np.ndarray, color, r=7):
    x, y = int(round(float(p[0]))), int(round(float(p[1])))
    cv2.circle(img_bgr, (x, y), r, color, -1, cv2.LINE_AA)
    cv2.circle(img_bgr, (x, y), r + 2, (255, 255, 255), 2, cv2.LINE_AA)
    return img_bgr


def overlay_inliers(mask_shape, inlier_pts: np.ndarray):
    h, w = mask_shape[:2]
    img = np.zeros((h, w), dtype=np.uint8)
    xs = np.clip(inlier_pts[:, 0].astype(np.int32), 0, w - 1)
    ys = np.clip(inlier_pts[:, 1].astype(np.int32), 0, h - 1)
    img[ys, xs] = 255
    return img


# -----------------------------
# Main pipeline
# -----------------------------
def estimate_4pts_from_mask(
    mask255: np.ndarray,
    base_vis: np.ndarray,
    out_dir: Path,
    args,
):
    """
    Returns dict points {TL,TR,BR,BL} float32
    """
    H, W = mask255.shape[:2]

    # 0) Preprocess / Edge
    m_open, m_dil, edge = build_edge_for_line_support(
        mask255,
        out_dir,
        prefix="00",
        open_ks=args.open_ks,
        dil_ks=args.dilate_ks,
    )

    # Choose which pixel set drives RANSAC:
    # - Using dilated mask tends to give more inliers -> stable
    # - Using edge gives less points but less background contamination
    # Default: use dilated mask pixels
    if args.use_edge_points:
        pts_src = edge
        tag = "edge"
    else:
        pts_src = m_dil
        tag = "mask"

    ys, xs = np.where(pts_src > 0)
    points = np.stack([xs, ys], axis=1).astype(np.float32)

    # Downsample points for speed if too many
    if points.shape[0] > args.max_points:
        rng = np.random.default_rng(123)
        idx = rng.choice(points.shape[0], size=args.max_points, replace=False)
        points = points[idx]

    # Save point density preview
    density = np.zeros((H, W), dtype=np.uint8)
    density[points[:, 1].astype(int), points[:, 0].astype(int)] = 255
    save_image(out_dir, f"01_points_{tag}_preview", density)

    # 1) RANSAC line #1
    fit1 = ransac_single_line(
        points=points,
        dist_th=args.dist_th,
        max_iter=args.ransac_iter,
        min_inliers=args.min_inliers,
        forbid_horizontal_deg=args.forbid_horizontal_deg,
    )
    if fit1 is None:
        raise RuntimeError("RANSAC failed to find first side line. Try increasing max_points / ransac_iter / dist_th.")

    p01, d1, n1, in1 = fit1
    pts1 = points[in1]
    img_in1 = overlay_inliers(mask255.shape, pts1)
    save_image(out_dir, "02_ransac1_inliers", img_in1)

    vis1 = base_vis.copy()
    draw_line_on_image(vis1, p01, d1, (0, 255, 255), thickness=3)
    save_image(out_dir, "03_ransac1_line_overlay", vis1)

    # Remove inliers and fit line #2
    remaining = points[~in1]
    fit2 = ransac_single_line(
        points=remaining,
        dist_th=args.dist_th,
        max_iter=args.ransac_iter,
        min_inliers=args.min_inliers,
        forbid_horizontal_deg=args.forbid_horizontal_deg,
    )
    if fit2 is None:
        raise RuntimeError("RANSAC failed to find second side line. Try increasing max_points / ransac_iter / dist_th.")

    p02, d2, n2, in2 = fit2
    pts2 = remaining[in2]
    img_in2 = overlay_inliers(mask255.shape, pts2)
    save_image(out_dir, "04_ransac2_inliers", img_in2)

    vis2 = base_vis.copy()
    draw_line_on_image(vis2, p01, d1, (0, 255, 255), thickness=3)
    draw_line_on_image(vis2, p02, d2, (255, 255, 0), thickness=3)
    save_image(out_dir, "05_two_lines_overlay", vis2)

    # 2) Decide Left/Right using x at y*
    y_star = float(args.y_star_ratio * H)
    x1 = x_at_y(p01, d1, y_star)
    x2 = x_at_y(p02, d2, y_star)
    if x1 is None or x2 is None:
        # If d.y is too small (almost horizontal), something is wrong; relax forbid_horizontal_deg or use different points set.
        raise RuntimeError("x_at_y failed: one of lines has near-zero dy. Check forbid_horizontal_deg or RANSAC result.")

    if x1 < x2:
        L_p0, L_d, L_pts = p01, d1, pts1
        R_p0, R_d, R_pts = p02, d2, pts2
    else:
        L_p0, L_d, L_pts = p02, d2, pts2
        R_p0, R_d, R_pts = p01, d1, pts1

    # --- DEBUG 1) top_subset_points_left/right 저장 ---
    L_top_subset, L_y_th = subset_by_top_percentile(L_pts, args.top_pct)
    R_top_subset, R_y_th = subset_by_top_percentile(R_pts, args.top_pct)

    img_L_top = overlay_inliers(mask255.shape, L_top_subset)
    img_R_top = overlay_inliers(mask255.shape, R_top_subset)
    save_image(out_dir, f"05A_top_subset_points_left_top{args.top_pct:g}pct", img_L_top)
    save_image(out_dir, f"05B_top_subset_points_right_top{args.top_pct:g}pct", img_R_top)

    # base 위에 색으로도 오버레이(분석 편의)
    vis_top = base_vis.copy()
    # left top subset = cyan, right top subset = yellow
    for pts, col in [(L_top_subset, (255, 255, 0)), (R_top_subset, (0, 255, 255))]:
        xs = np.clip(pts[:, 0].astype(np.int32), 0, W - 1)
        ys = np.clip(pts[:, 1].astype(np.int32), 0, H - 1)
        vis_top[ys, xs] = col

    cv2.putText(vis_top, f"L top y_th={L_y_th:.1f}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(vis_top, f"R top y_th={R_y_th:.1f}", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)

    save_image(out_dir, f"05C_top_subset_overlay_on_base", vis_top)

    # 3) Endpoints with paired-top constraint
    TL, TR, BL, BR, used_top_pct, top_dy = enforce_paired_top_constraint(
        L_inliers=L_pts,
        R_inliers=R_pts,
        L_p0=L_p0, L_d=L_d,
        R_p0=R_p0, R_d=R_d,
        top_pct_init=args.top_pct,
        bot_pct=args.bot_pct,
        max_top_y_diff=args.max_top_y_diff,
    )

    # --- DEBUG 2) endpoint_segment_overlay 저장 (inlier 투영 구간 선분) ---
    # 각 라인에서 inlier 전체를 대상으로 투영 극값으로 segment endpoints 산출
    L_seg_a, L_seg_b = project_endpoints(L_pts, L_p0, L_d)
    R_seg_a, R_seg_b = project_endpoints(R_pts, R_p0, R_d)

    vis_seg = base_vis.copy()

    # Left/Right segment를 각각 선분으로만 표시
    draw_segment(vis_seg, L_seg_a, L_seg_b, (255, 255, 0), thickness=4)  # Left: cyan-ish
    draw_segment(vis_seg, R_seg_a, R_seg_b, (0, 255, 255), thickness=4)  # Right: yellow-ish

    # segment 끝점도 찍어두면 "어디서 끊겼는지" 판단 쉬움
    draw_point(vis_seg, L_seg_a, (255, 255, 0), r=6)
    draw_point(vis_seg, L_seg_b, (255, 255, 0), r=6)
    draw_point(vis_seg, R_seg_a, (0, 255, 255), r=6)
    draw_point(vis_seg, R_seg_b, (0, 255, 255), r=6)

    # 최종 TL/TR/BL/BR도 같이 표시(비교용)
    draw_point(vis_seg, TL, (0, 0, 255), r=8)
    draw_point(vis_seg, TR, (0, 255, 0), r=8)
    draw_point(vis_seg, BL, (0, 0, 255), r=8)
    draw_point(vis_seg, BR, (0, 255, 0), r=8)

    cv2.putText(vis_seg, "Segment overlay (t_min~t_max on inliers)", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2, cv2.LINE_AA)

    save_image(out_dir, "06D_endpoint_segment_overlay", vis_seg)

    # 4) Final visualization: endpoints + quad
    vis_end = base_vis.copy()
    draw_line_on_image(vis_end, L_p0, L_d, (0, 255, 255), thickness=3)
    draw_line_on_image(vis_end, R_p0, R_d, (255, 255, 0), thickness=3)

    draw_point(vis_end, TL, (0, 0, 255))      # TL red
    draw_point(vis_end, TR, (0, 255, 0))      # TR green
    draw_point(vis_end, BL, (0, 0, 255))      # BL red
    draw_point(vis_end, BR, (0, 255, 0))      # BR green

    save_image(out_dir, "06_endpoints_overlay", vis_end)

    vis_quad = vis_end.copy()
    quad = np.array([TL, TR, BR, BL], dtype=np.int32)
    cv2.polylines(vis_quad, [quad], True, (255, 0, 255), 3, cv2.LINE_AA)
    save_image(out_dir, "07_quad_overlay", vis_quad)

    # 5) Save coordinates
    pts_dict = {"TL": TL, "TR": TR, "BR": BR, "BL": BL}
    txt = out_dir / "estimated_4points.txt"
    with open(txt, "w") as f:
        f.write("Estimated 4 points from side-lines only\n")
        f.write(f"top_pct_used: {used_top_pct:.4f}\n")
        f.write(f"top_y_diff: {top_dy:.2f}px\n")
        f.write(f"y_star: {y_star:.2f}\n")
        for k in ["TL", "TR", "BR", "BL"]:
            p = pts_dict[k]
            f.write(f"{k}: {float(p[0]):.6f}, {float(p[1]):.6f}\n")
    print(f"[SAVED] {txt}")

    # Also save a compact JSON-like file
    txt2 = out_dir / "estimated_4points_compact.txt"
    with open(txt2, "w") as f:
        f.write(
            "{"
            + ", ".join([f'"{k}":[{float(pts_dict[k][0]):.3f},{float(pts_dict[k][1]):.3f}]' for k in ["TL", "TR", "BR", "BL"]])
            + "}\n"
        )
    print(f"[SAVED] {txt2}")

    return pts_dict


def main():
    parser = argparse.ArgumentParser(description="Estimate TL/TR/BR/BL using only 2 outer side-lines from A_00 mask.")
    parser.add_argument("--mask_input", required=True, help="Path to A_00 mask image (binary-ish).")
    parser.add_argument("--original_input", default=None, help="(Optional) original frame image path for nicer overlays.")
    parser.add_argument("--out_root", required=True, help="Root directory to save results. A new run folder will be created.")

    # Minimal preprocessing knobs
    # parser.add_argument("--open_ks", type=int, default=3, help="Weak open kernel size (odd). 0 to disable.")
    parser.add_argument("--open_ks", type=int, default=0, help="Weak open kernel size (odd). 0 to disable.")
    parser.add_argument("--dilate_ks", type=int, default=3, help="Weak dilate kernel size (odd). 0 to disable.")
    parser.add_argument("--use_edge_points", action="store_true", help="Use edge pixels (morph gradient) as RANSAC points instead of mask pixels.")

    # RANSAC knobs
    parser.add_argument("--dist_th", type=float, default=3.5, help="Inlier distance threshold in pixels.")
    parser.add_argument("--ransac_iter", type=int, default=2500, help="RANSAC iterations.")
    parser.add_argument("--min_inliers", type=int, default=450, help="Minimum inliers to accept a line.")
    parser.add_argument("--forbid_horizontal_deg", type=float, default=15.0, help="Reject near-horizontal lines within this deg from 0/180.")
    parser.add_argument("--max_points", type=int, default=120000, help="Max sampled points for RANSAC speed.")

    # Endpoint robustness knobs
    parser.add_argument("--top_pct", type=float, default=3.0, help="Top y-percentile used to pick upper endpoint subset (smaller => more upper).")
    parser.add_argument("--bot_pct", type=float, default=97.0, help="Bottom y-percentile used to pick lower endpoint subset.")
    parser.add_argument("--max_top_y_diff", type=float, default=90.0, help="Max allowed |TL.y - TR.y|. If larger, tighten top_pct iteratively.")
    parser.add_argument("--y_star_ratio", type=float, default=0.85, help="y* ratio for left/right decision using x-at-y*.")

    args = parser.parse_args()

    mask_path = Path(args.mask_input)
    if not mask_path.exists():
        raise FileNotFoundError(f"Mask image not found: {mask_path}")

    mask_in = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
    if mask_in is None:
        raise ValueError(f"Failed to read mask: {mask_path}")

    out_dir = make_output_dir(args.out_root)
    print(f"[INFO] Output directory: {out_dir}")

    # Normalize mask to 0/255
    mask255 = normalize_mask_to_255(mask_in)
    save_image(out_dir, "A00_mask_input_norm255", mask255)

    H, W = mask255.shape[:2]

    # Base visualization background
    if args.original_input is not None:
        orig_path = Path(args.original_input)
        if not orig_path.exists():
            raise FileNotFoundError(f"Original image not found: {orig_path}")
        base = cv2.imread(str(orig_path), cv2.IMREAD_COLOR)
        if base is None:
            raise ValueError(f"Failed to read original: {orig_path}")
        if base.shape[0] != H or base.shape[1] != W:
            base = cv2.resize(base, (W, H), interpolation=cv2.INTER_LINEAR)
        save_image(out_dir, "A01_original_for_overlay", base)
    else:
        base = to_bgr(mask255)
        save_image(out_dir, "A01_overlay_base_is_mask", base)

    # Run pipeline
    pts = estimate_4pts_from_mask(mask255, base, out_dir, args)

    print("\n[RESULT] 4 points (float pixel coords):")
    for k in ["TL", "TR", "BR", "BL"]:
        p = pts[k]
        print(f"  {k}: ({float(p[0]):.2f}, {float(p[1]):.2f})")

    print(f"\n[DONE] Saved all debug images to: {out_dir}")


if __name__ == "__main__":
    main()


"""
python pl_1_ransac.py \
  --mask_input source_image/pro_mask_raw.png \
  --out_root pl1_results

# 1
python pl_1_ransac.py \
  --mask_input source_image/pro_mask_raw.png \
  --original_input source_image/pro_court.png \
  --out_root pl1_results \
  --open_ks 0 \
  --dilate_ks 0 \
  --dist_th 3.5 \
  --min_inliers 180 \
  --ransac_iter 5000 \
  --top_pct 2.0 \
  --max_top_y_diff 60


# 상단 검출 방지
python pl_1_ransac.py \
  --mask_input source_image/pro_mask_raw.png \
  --original_input source_image/pro_court.png \
  --out_root pl1_results \
  --open_ks 0 \
  --dilate_ks 0 \
  --dist_th 3.0 \
  --min_inliers 140 \
  --ransac_iter 7000 \
  --top_pct 1.5 \
  --max_top_y_diff 50
"""