import argparse
import datetime
import uuid
from pathlib import Path
import zipfile
import math

import cv2
import numpy as np


# ----------------------------
# Utils: output, saving
# ----------------------------
def make_out_dir(root: str = "results_lines") -> Path:
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    out_dir = Path.cwd() / root / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def save_png(out_dir: Path, name: str, img: np.ndarray) -> Path:
    p = out_dir / f"{name}.png"
    cv2.imwrite(str(p), img)
    return p


def ensure_gray_u8(img):
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return img


# ----------------------------
# Thinning (Zhang-Suen) - no opencv-contrib dependency
# ----------------------------
def zhang_suen_thinning(bin_img: np.ndarray, max_iter: int = 100) -> np.ndarray:
    """
    bin_img: uint8 {0,255}
    returns skeleton uint8 {0,255}
    """
    img = (bin_img > 0).astype(np.uint8)
    h, w = img.shape[:2]

    def neighbors(x, y):
        # p2 p3 p4
        # p9 p1 p5
        # p8 p7 p6
        p2 = img[x-1, y]
        p3 = img[x-1, y+1]
        p4 = img[x, y+1]
        p5 = img[x+1, y+1]
        p6 = img[x+1, y]
        p7 = img[x+1, y-1]
        p8 = img[x, y-1]
        p9 = img[x-1, y-1]
        return [p2,p3,p4,p5,p6,p7,p8,p9]

    def transitions(P):
        # count 0->1 transitions in circular sequence
        n = 0
        for i in range(8):
            if P[i] == 0 and P[(i+1) % 8] == 1:
                n += 1
        return n

    changed = True
    it = 0
    while changed and it < max_iter:
        changed = False
        it += 1
        to_remove = []

        # step 1
        for x in range(1, h-1):
            for y in range(1, w-1):
                if img[x, y] != 1:
                    continue
                P = neighbors(x, y)
                B = sum(P)
                A = transitions(P)
                p2,p3,p4,p5,p6,p7,p8,p9 = P
                if (2 <= B <= 6 and A == 1 and p2*p4*p6 == 0 and p4*p6*p8 == 0):
                    to_remove.append((x, y))
        if to_remove:
            for x, y in to_remove:
                img[x, y] = 0
            changed = True

        to_remove = []
        # step 2
        for x in range(1, h-1):
            for y in range(1, w-1):
                if img[x, y] != 1:
                    continue
                P = neighbors(x, y)
                B = sum(P)
                A = transitions(P)
                p2,p3,p4,p5,p6,p7,p8,p9 = P
                if (2 <= B <= 6 and A == 1 and p2*p4*p8 == 0 and p2*p6*p8 == 0):
                    to_remove.append((x, y))
        if to_remove:
            for x, y in to_remove:
                img[x, y] = 0
            changed = True

    return (img * 255).astype(np.uint8)


# ----------------------------
# Line segment detection & clustering
# ----------------------------
def segments_from_hough(skel: np.ndarray, min_len=40, max_gap=10, thresh=60):
    """
    Use HoughLinesP on skeleton; returns segments [x1,y1,x2,y2]
    """
    edges = skel.copy()
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=thresh,
                            minLineLength=min_len, maxLineGap=max_gap)
    segs = []
    if lines is not None:
        for l in lines[:, 0, :]:
            segs.append(l.astype(int).tolist())
    return segs


def segment_angle_deg(seg):
    x1,y1,x2,y2 = seg
    dx = x2 - x1
    dy = y2 - y1
    ang = math.degrees(math.atan2(dy, dx))  # -180..180
    # map to [0,180)
    ang = ang % 180.0
    return ang


def kmeans_two_angle_clusters(segs):
    """
    cluster by orientation using (cos2θ, sin2θ) trick (θ and θ+180 same)
    return cluster_ids, cluster_mean_angles_deg[2]
    """
    if len(segs) == 0:
        return [], []

    feats = []
    for s in segs:
        th = math.radians(segment_angle_deg(s))
        feats.append([math.cos(2*th), math.sin(2*th)])
    feats = np.array(feats, dtype=np.float32)

    # if too few segments, all to one cluster
    if len(segs) < 4:
        return [0]*len(segs), [segment_angle_deg(segs[0]), segment_angle_deg(segs[0])]

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3)
    _, labels, centers = cv2.kmeans(feats, 2, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    labels = labels.flatten().tolist()

    # derive mean angles from centers
    mean_angles = []
    for c in centers:
        # recover 2θ from (cos2θ,sin2θ)
        two = math.atan2(float(c[1]), float(c[0]))
        th = two / 2.0
        ang = (math.degrees(th) % 180.0)
        mean_angles.append(ang)

    return labels, mean_angles


def draw_segments_overlay(img_bgr, segs, labels=None, colors=None, alpha=0.7):
    out = img_bgr.copy()
    overlay = img_bgr.copy()
    for i, s in enumerate(segs):
        x1,y1,x2,y2 = s
        if labels is None or colors is None:
            col = (0,255,0)
        else:
            col = colors[labels[i] % len(colors)]
        cv2.line(overlay, (x1,y1), (x2,y2), col, 2, cv2.LINE_AA)
    return cv2.addWeighted(overlay, alpha, out, 1-alpha, 0)


# ----------------------------
# Parallel line extraction via rho peaks
# ----------------------------
def compute_rho_for_segments(segs, theta_line_rad):
    """
    For a given line direction angle theta_line (in radians),
    normal vector is (-sin, cos). rho = n·midpoint
    """
    nx = -math.sin(theta_line_rad)
    ny =  math.cos(theta_line_rad)
    rhos = []
    mids = []
    for s in segs:
        x1,y1,x2,y2 = s
        mx = 0.5*(x1+x2)
        my = 0.5*(y1+y2)
        rho = mx*nx + my*ny
        rhos.append(rho)
        mids.append((mx,my))
    return np.array(rhos, dtype=np.float32), np.array(mids, dtype=np.float32)


def smooth_1d(arr, k=9):
    k = max(3, int(k))
    if k % 2 == 0:
        k += 1
    ker = np.ones(k, dtype=np.float32) / k
    return np.convolve(arr, ker, mode="same")


def find_peaks_1d(y, min_prom=0.15, min_dist=8):
    """
    simple local maxima finder on normalized y
    """
    if len(y) < 3:
        return []
    y = np.array(y, dtype=np.float32)
    y_min = float(y.min())
    y_max = float(y.max())
    if y_max - y_min < 1e-6:
        return []
    yn = (y - y_min) / (y_max - y_min + 1e-6)

    peaks = []
    for i in range(1, len(yn)-1):
        if yn[i] > yn[i-1] and yn[i] > yn[i+1] and yn[i] >= min_prom:
            peaks.append(i)

    # enforce min distance
    filtered = []
    for p in peaks:
        if not filtered:
            filtered.append(p)
        else:
            if all(abs(p - q) >= min_dist for q in filtered):
                filtered.append(p)
    return filtered


def fit_line_tls(points_xy):
    """
    Total least squares line fit.
    Return line in ax+by+c=0 with normalized (a,b).
    """
    pts = np.asarray(points_xy, dtype=np.float32)
    if len(pts) < 2:
        return None
    c = pts.mean(axis=0)
    X = pts - c
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    direction = vt[0]  # principal direction
    dx, dy = float(direction[0]), float(direction[1])
    # normal
    a = -dy
    b = dx
    norm = math.hypot(a, b) + 1e-9
    a /= norm
    b /= norm
    c0 = -(a*c[0] + b*c[1])
    return (a, b, c0)


def line_intersections_with_image(a, b, c, w, h):
    """
    return up to 2 intersection points of ax+by+c=0 with image rectangle.
    """
    pts = []
    # x=0 => b*y + c = 0
    if abs(b) > 1e-9:
        y = -(c) / b
        if 0 <= y <= h-1:
            pts.append((0, int(round(y))))
    # x=w-1
    if abs(b) > 1e-9:
        y = -(a*(w-1) + c) / b
        if 0 <= y <= h-1:
            pts.append((w-1, int(round(y))))
    # y=0
    if abs(a) > 1e-9:
        x = -(c) / a
        if 0 <= x <= w-1:
            pts.append((int(round(x)), 0))
    # y=h-1
    if abs(a) > 1e-9:
        x = -(b*(h-1) + c) / a
        if 0 <= x <= w-1:
            pts.append((int(round(x)), h-1))

    # unique and keep first two farthest
    uniq = []
    for p in pts:
        if p not in uniq:
            uniq.append(p)
    if len(uniq) <= 2:
        return uniq
    # choose farthest pair
    best = (uniq[0], uniq[1])
    best_d = -1
    for i in range(len(uniq)):
        for j in range(i+1, len(uniq)):
            dx = uniq[i][0]-uniq[j][0]
            dy = uniq[i][1]-uniq[j][1]
            d = dx*dx+dy*dy
            if d > best_d:
                best_d = d
                best = (uniq[i], uniq[j])
    return [best[0], best[1]]


def rho_hist_image(rhos, bins=120, width=900, height=220, peaks=None, title="rho_hist"):
    if rhos.size == 0:
        img = np.zeros((height, width, 3), np.uint8)
        cv2.putText(img, "No rhos", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2, cv2.LINE_AA)
        return img

    hist, edges = np.histogram(rhos, bins=bins)
    hist = hist.astype(np.float32)
    hist_s = smooth_1d(hist, k=9)
    hist_s = hist_s / (hist_s.max() + 1e-6)

    img = np.zeros((height, width, 3), np.uint8)
    # draw axis
    cv2.line(img, (40, height-30), (width-20, height-30), (200,200,200), 1)
    cv2.line(img, (40, 20), (40, height-30), (200,200,200), 1)

    # plot
    x0 = 40
    x1 = width-20
    y0 = height-30
    plot_w = x1-x0
    plot_h = y0-20
    n = len(hist_s)
    for i in range(n-1):
        px1 = x0 + int(plot_w * (i/(n-1)))
        py1 = y0 - int(plot_h * hist_s[i])
        px2 = x0 + int(plot_w * ((i+1)/(n-1)))
        py2 = y0 - int(plot_h * hist_s[i+1])
        cv2.line(img, (px1,py1), (px2,py2), (0,255,255), 2, cv2.LINE_AA)

    if peaks:
        for p in peaks:
            px = x0 + int(plot_w * (p/(n-1)))
            cv2.line(img, (px, 20), (px, y0), (0,0,255), 1, cv2.LINE_AA)

    cv2.putText(img, title, (40, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
    return img


def extract_parallel_lines_from_cluster(
    segs, mean_angle_deg, w, h,
    peak_bins=140,
    rho_tol=14.0,
    max_lines=6,
    peak_min_prom=0.20,
    peak_min_dist=10
):
    """
    For one orientation cluster:
    - compute rhos
    - histogram peaks
    - for each peak, collect points and TLS fit line
    """
    if len(segs) == 0:
        return [], None, None

    theta = math.radians(mean_angle_deg)
    rhos, _ = compute_rho_for_segments(segs, theta)

    # histogram & peaks
    hist, edges = np.histogram(rhos, bins=peak_bins)
    hist_s = smooth_1d(hist.astype(np.float32), k=9)
    peaks_idx = find_peaks_1d(hist_s, min_prom=peak_min_prom, min_dist=peak_min_dist)

    # sort peaks by smoothed count (desc), keep top max_lines, then sort by rho position
    peaks_idx = sorted(peaks_idx, key=lambda i: float(hist_s[i]), reverse=True)[:max_lines]
    peaks_idx = sorted(peaks_idx)

    peak_rhos = []
    for pi in peaks_idx:
        # bin center
        r0 = 0.5*(edges[pi] + edges[pi+1])
        peak_rhos.append(float(r0))

    fitted = []
    for r0 in peak_rhos:
        pts = []
        for s in segs:
            x1,y1,x2,y2 = s
            mx = 0.5*(x1+x2)
            my = 0.5*(y1+y2)
            nx = -math.sin(theta)
            ny =  math.cos(theta)
            rho = mx*nx + my*ny
            if abs(rho - r0) <= rho_tol:
                pts.append((x1,y1))
                pts.append((x2,y2))

        line = fit_line_tls(pts)
        if line is None:
            continue
        a,b,c = line
        pts2 = line_intersections_with_image(a,b,c,w,h)
        if len(pts2) == 2:
            fitted.append({"abc": (a,b,c), "p1": pts2[0], "p2": pts2[1], "rho": r0})

    # remove near-duplicate lines by rho proximity
    fitted = sorted(fitted, key=lambda d: d["rho"])
    dedup = []
    for L in fitted:
        if not dedup:
            dedup.append(L)
        else:
            if abs(L["rho"] - dedup[-1]["rho"]) > (rho_tol * 0.8):
                dedup.append(L)

    return dedup, rhos, peaks_idx


# ----------------------------
# Labeling heuristics (no homography yet)
# ----------------------------
def line_y_at_x(abc, x):
    a,b,c = abc
    if abs(b) < 1e-9:
        return None
    return float(-(a*x + c)/b)


def line_x_at_y(abc, y):
    a,b,c = abc
    if abs(a) < 1e-9:
        return None
    return float(-(b*y + c)/a)


def label_lengthwise_lines(lines, w, h):
    """
    lengthwise group: "sidelines + center line" (mostly vertical in image)
    Label by x-position at y=0.75h
    """
    y_ref = int(0.75*h)
    xs = []
    for L in lines:
        x = line_x_at_y(L["abc"], y_ref)
        if x is None:
            x = (L["p1"][0] + L["p2"][0]) / 2.0
        xs.append((x, L))
    xs.sort(key=lambda t: t[0])

    labeled = []
    n = len(xs)
    if n == 0:
        return labeled

    # choose best mapping depending on count
    if n >= 5:
        # [LD, LS, C, RS, RD]
        names = ["doubles_sideline_L", "singles_sideline_L", "center_line",
                 "singles_sideline_R", "doubles_sideline_R"]
        # if more than 5, pick 5 most "spread" around center by selecting extremes + nearest pairs
        # simplest: take 5 by evenly sampling
        idxs = np.linspace(0, n-1, 5).round().astype(int).tolist()
        sel = [xs[i] for i in idxs]
        sel.sort(key=lambda t: t[0])
        for nm, (_, L) in zip(names, sel):
            labeled.append((nm, L))
    elif n == 3:
        names = ["doubles_sideline_L", "center_line", "doubles_sideline_R"]
        for nm, (_, L) in zip(names, xs):
            labeled.append((nm, L))
    elif n == 2:
        names = ["doubles_sideline_L", "doubles_sideline_R"]
        for nm, (_, L) in zip(names, xs):
            labeled.append((nm, L))
    else:
        # fallback: label extremes as doubles, middle as center if exists
        labeled.append(("doubles_sideline_L", xs[0][1]))
        if n > 2:
            labeled.append(("center_line", xs[n//2][1]))
        labeled.append(("doubles_sideline_R", xs[-1][1]))

    return labeled


def label_crosswise_lines(lines, w, h):
    """
    crosswise group: "baselines + service lines" (mostly horizontal in image)
    Label by y-position at x=w/2, bottom->top
    """
    x_ref = int(w/2)
    ys = []
    for L in lines:
        y = line_y_at_x(L["abc"], x_ref)
        if y is None:
            y = (L["p1"][1] + L["p2"][1]) / 2.0
        ys.append((y, L))
    ys.sort(key=lambda t: t[0], reverse=True)  # bottom first

    labeled = []
    n = len(ys)
    if n == 0:
        return labeled

    # Expect potentially: baseline_near, long_service_near, short_service_near,
    # short_service_far, long_service_far, baseline_far  (6)
    if n >= 6:
        names = ["baseline_near",
                 "long_service_doubles_near",
                 "short_service_near",
                 "short_service_far",
                 "long_service_doubles_far",
                 "baseline_far"]
        sel = ys[:6]
        for nm, (_, L) in zip(names, sel):
            labeled.append((nm, L))
    elif n == 4:
        names = ["baseline_near", "short_service_near", "short_service_far", "baseline_far"]
        for nm, (_, L) in zip(names, ys):
            labeled.append((nm, L))
    elif n == 2:
        names = ["baseline_near", "baseline_far"]
        for nm, (_, L) in zip(names, ys):
            labeled.append((nm, L))
    else:
        # generic: label by order
        for i, (_, L) in enumerate(ys):
            labeled.append((f"cross_line_{i}", L))

    return labeled


# ----------------------------
# Final overlay with colors + labels
# ----------------------------
def color_map_bgr():
    return {
        "center_line": (0, 255, 255),                 # yellow
        "singles_sideline_L": (255, 0, 0),            # blue
        "singles_sideline_R": (255, 0, 0),
        "doubles_sideline_L": (0, 255, 0),            # green
        "doubles_sideline_R": (0, 255, 0),
        "baseline_near": (0, 0, 255),                 # red
        "baseline_far": (0, 0, 255),
        "short_service_near": (255, 255, 0),          # cyan
        "short_service_far": (255, 255, 0),
        "long_service_doubles_near": (255, 0, 255),   # magenta
        "long_service_doubles_far": (255, 0, 255),
    }


def put_label(img, text, x, y, color=(255,255,255)):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,0,0), 3, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)


def draw_labeled_lines(img_bgr, labeled_lines, thickness=3):
    out = img_bgr.copy()
    cmap = color_map_bgr()

    for name, L in labeled_lines:
        col = cmap.get(name, (200, 200, 200))
        p1, p2 = L["p1"], L["p2"]
        cv2.line(out, p1, p2, col, thickness, cv2.LINE_AA)

        # label near p1 (shift a bit)
        lx = int(p1[0] + 8)
        ly = int(p1[1] - 8)
        put_label(out, name, lx, max(20, ly), col)

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Original image path (BGR)")
    parser.add_argument("--mask", required=True, help="Binary mask path (e.g., 99_final_white_line_mask.png)")
    parser.add_argument("--out_root", default="results_lines", help="Output root dir under CWD")
    parser.add_argument("--zip", action="store_true")

    # skeleton / hough params
    parser.add_argument("--thin_iter", type=int, default=80, help="Max thinning iterations")
    parser.add_argument("--hough_thresh", type=int, default=60)
    parser.add_argument("--min_len", type=int, default=60)
    parser.add_argument("--max_gap", type=int, default=12)

    # rho peak params
    parser.add_argument("--peak_bins", type=int, default=140)
    parser.add_argument("--rho_tol", type=float, default=14.0)
    parser.add_argument("--max_lines_each", type=int, default=7)
    parser.add_argument("--peak_min_prom", type=float, default=0.20)
    parser.add_argument("--peak_min_dist", type=int, default=10)

    args = parser.parse_args()

    out_dir = make_out_dir(args.out_root)
    print(f"[INFO] Output dir: {out_dir}")

    img = cv2.imread(args.input)
    if img is None:
        raise FileNotFoundError(f"Failed to read input: {args.input}")

    mask = cv2.imread(args.mask, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise FileNotFoundError(f"Failed to read mask: {args.mask}")

    h, w = img.shape[:2]
    mask = (mask > 0).astype(np.uint8) * 255

    save_png(out_dir, "00_original", img)
    save_png(out_dir, "01_mask_input", mask)

    # 1) thinning
    skel = zhang_suen_thinning(mask, max_iter=args.thin_iter)
    save_png(out_dir, "02_skeleton", skel)

    # 2) Hough segments
    segs = segments_from_hough(skel, min_len=args.min_len, max_gap=args.max_gap, thresh=args.hough_thresh)
    seg_overlay = draw_segments_overlay(img, segs, labels=None, colors=None, alpha=0.8)
    save_png(out_dir, "03_segments_overlay", seg_overlay)

    # 3) angle clustering (2 clusters)
    seg_labels, mean_angles = kmeans_two_angle_clusters(segs)
    cluster_colors = [(0,255,0), (0,0,255)]
    seg_cluster_overlay = draw_segments_overlay(img, segs, labels=seg_labels, colors=cluster_colors, alpha=0.8)
    save_png(out_dir, "04_segments_angle_clusters", seg_cluster_overlay)

    if len(mean_angles) != 2:
        # fallback: just save and finish
        final = img.copy()
        put_label(final, "Not enough segments for clustering", 30, 40, (0,0,255))
        save_png(out_dir, "99_final_labeled_lines", final)
        print("[WARN] Not enough segments.")
        return

    # split segments per cluster
    segs0 = [s for s, lb in zip(segs, seg_labels) if lb == 0]
    segs1 = [s for s, lb in zip(segs, seg_labels) if lb == 1]

    # 4) extract parallel lines per cluster using rho peaks
    lines0, rhos0, peaks0 = extract_parallel_lines_from_cluster(
        segs0, mean_angles[0], w, h,
        peak_bins=args.peak_bins, rho_tol=args.rho_tol,
        max_lines=args.max_lines_each,
        peak_min_prom=args.peak_min_prom, peak_min_dist=args.peak_min_dist
    )
    lines1, rhos1, peaks1 = extract_parallel_lines_from_cluster(
        segs1, mean_angles[1], w, h,
        peak_bins=args.peak_bins, rho_tol=args.rho_tol,
        max_lines=args.max_lines_each,
        peak_min_prom=args.peak_min_prom, peak_min_dist=args.peak_min_dist
    )

    # rho hist debug
    if rhos0 is not None:
        img_hist0 = rho_hist_image(rhos0, bins=args.peak_bins, peaks=peaks0, title="rho_hist_cluster0")
        save_png(out_dir, "05_rho_hist_cluster0", img_hist0)
    if rhos1 is not None:
        img_hist1 = rho_hist_image(rhos1, bins=args.peak_bins, peaks=peaks1, title="rho_hist_cluster1")
        save_png(out_dir, "06_rho_hist_cluster1", img_hist1)

    # draw extracted raw lines per cluster
    raw_lines_overlay = img.copy()
    for L in lines0:
        cv2.line(raw_lines_overlay, L["p1"], L["p2"], (0,255,0), 2, cv2.LINE_AA)
    for L in lines1:
        cv2.line(raw_lines_overlay, L["p1"], L["p2"], (0,0,255), 2, cv2.LINE_AA)
    save_png(out_dir, "07_parallel_lines_by_cluster", raw_lines_overlay)

    # 5) decide which cluster is lengthwise (more vertical)
    # Use mean angle: closer to 90deg => vertical-ish
    def vertical_score(angle_deg):
        # 0: horizontal, 90: vertical
        return abs(angle_deg - 90.0)

    # smaller diff to 90 => more vertical
    is0_vertical = vertical_score(mean_angles[0]) < vertical_score(mean_angles[1])
    if is0_vertical:
        lengthwise = lines0
        crosswise = lines1
    else:
        lengthwise = lines1
        crosswise = lines0

    # 6) label heuristics
    labeled_len = label_lengthwise_lines(lengthwise, w, h)
    labeled_crs = label_crosswise_lines(crosswise, w, h)

    # progress: draw labeled groups separately
    img_len = draw_labeled_lines(img, labeled_len, thickness=3)
    save_png(out_dir, "08_labeled_lengthwise", img_len)

    img_crs = draw_labeled_lines(img, labeled_crs, thickness=3)
    save_png(out_dir, "09_labeled_crosswise", img_crs)

    # 7) final combined overlay
    labeled_all = labeled_len + labeled_crs
    final = draw_labeled_lines(img, labeled_all, thickness=4)
    save_png(out_dir, "99_final_labeled_lines", final)

    # zip optional
    if args.zip:
        zip_path = out_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out_dir.glob("*.png")):
                z.write(p, arcname=p.name)
        print(f"[INFO] Zipped: {zip_path}")

    print("[DONE]")


if __name__ == "__main__":
    main()


"""
python get_linemask_v3.py \
  --input fullcourt_wide.jpg \
  --mask 99_final_white_line_mask.png \
  --out_root results_lines 
"""


