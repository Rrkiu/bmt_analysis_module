import argparse
import datetime
import uuid
from pathlib import Path
import zipfile
import json
import math

import cv2
import numpy as np

import csv
import math


# ============================================================
# IO utils
# ============================================================
def make_out_dir(root: str = "results_full") -> Path:
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    out_dir = Path.cwd() / root / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def save_png(out_dir: Path, name: str, img: np.ndarray) -> Path:
    p = out_dir / f"{name}.png"
    cv2.imwrite(str(p), img)
    return p


def save_json(out_dir: Path, name: str, obj) -> Path:
    p = out_dir / f"{name}.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return p


def ensure_odd_positive(x: int, minimum: int = 1) -> int:
    x = max(int(x), int(minimum))
    if x % 2 == 0:
        x += 1
    return x


def _seg_get_p1p2(seg):
    """
    seg가 dict({"p1":(x,y),"p2":(x,y)}) 이거나,
    (x1,y1,x2,y2) 같은 list/tuple 형태여도 모두 처리.
    """
    if isinstance(seg, dict):
        p1 = seg["p1"]
        p2 = seg["p2"]
        return (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))
    # list/tuple
    if isinstance(seg, (list, tuple)):
        if len(seg) == 4:
            x1, y1, x2, y2 = seg
            return (int(x1), int(y1)), (int(x2), int(y2))
        if len(seg) == 2 and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in seg):
            p1, p2 = seg
            return (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))
    raise TypeError(f"Unknown segment format: {type(seg)} / {seg}")

def segment_angle_signed_deg(seg):
    """
    부호 포함 각도 [-90, +90) 로 정규화.
    - 수평: 0 근처
    - 우상향(양의 기울기): +각
    - 좌상향(음의 기울기): -각
    """
    (x1, y1), (x2, y2) = _seg_get_p1p2(seg)
    dx = x2 - x1
    dy = y2 - y1
    th = math.degrees(math.atan2(dy, dx))  # [-180,180]
    # 방향성 없는 "선"으로 보고 [-90,90)로 접기
    while th < -90.0:
        th += 180.0
    while th >= 90.0:
        th -= 180.0
    return th

def cluster_segments_3way_signed(segs, horiz_thr_deg=20.0):
    """
    3분류(결정적 규칙):
      label 0: 가로(|theta| <= horiz_thr)
      label 1: 우사선(theta > horiz_thr)
      label 2: 좌사선(theta < -horiz_thr)
    반환:
      labels(list[int]), stats(dict)
    """
    labels = []
    thetas = []
    for s in segs:
        th = segment_angle_signed_deg(s)
        thetas.append(th)
        if abs(th) <= horiz_thr_deg:
            labels.append(0)
        elif th > 0:
            labels.append(1)
        else:
            labels.append(2)

    # 로그용 통계
    cnt0 = sum(1 for t in labels if t == 0)
    cnt1 = sum(1 for t in labels if t == 1)
    cnt2 = sum(1 for t in labels if t == 2)
    stats = {
        "horiz_thr_deg": float(horiz_thr_deg),
        "count_horiz": int(cnt0),
        "count_pos_slope": int(cnt1),
        "count_neg_slope": int(cnt2),
        "theta_min": float(np.min(thetas)) if len(thetas) else None,
        "theta_max": float(np.max(thetas)) if len(thetas) else None,
        "theta_mean": float(np.mean(thetas)) if len(thetas) else None,
    }
    return labels, stats

def save_segments_csv(path, segs, labels=None, W=None, H=None):
    """
    디버그용 CSV 저장: seg 포맷(dict/tuple) 모두 대응.
    """
    path = str(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow([
            "idx","label",
            "x1","y1","x2","y2",
            "dx","dy","len",
            "mid_x","mid_y",
            "theta_signed_deg",
            "W","H"
        ])
        for i, s in enumerate(segs):
            (x1,y1),(x2,y2) = _seg_get_p1p2(s)
            dx = x2 - x1
            dy = y2 - y1
            L = math.hypot(dx, dy)
            mx = 0.5*(x1+x2)
            my = 0.5*(y1+y2)
            th = segment_angle_signed_deg(s)
            lab = labels[i] if (labels is not None and i < len(labels)) else ""
            wr.writerow([i, lab, x1,y1,x2,y2, dx,dy, f"{L:.3f}", f"{mx:.2f}", f"{my:.2f}", f"{th:.3f}", W, H])

def draw_segments_overlay_with_angle_text(bgr, segs, labels=None, colors=None, topN=60):
    """
    각도 텍스트까지 찍는 디버그 오버레이(길이 상위 topN만).
    """
    overlay = bgr.copy()
    # 세그먼트 길이로 정렬
    lens = []
    for i, s in enumerate(segs):
        (x1,y1),(x2,y2) = _seg_get_p1p2(s)
        L = (x2-x1)**2 + (y2-y1)**2
        lens.append((L, i))
    lens.sort(reverse=True)
    keep = set(i for _, i in lens[:min(topN, len(lens))])

    if colors is None:
        colors = [(0,255,0),(0,0,255),(255,0,0)]
    if labels is None:
        labels = [0]*len(segs)

    for i, s in enumerate(segs):
        (x1,y1),(x2,y2) = _seg_get_p1p2(s)
        c = colors[labels[i] % len(colors)]
        cv2.line(overlay, (x1,y1), (x2,y2), c, 2, cv2.LINE_AA)

        if i in keep:
            th = segment_angle_signed_deg(s)
            mx = int(0.5*(x1+x2))
            my = int(0.5*(y1+y2))
            cv2.putText(
                overlay,
                f"{th:+.1f}",
                (mx, my),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                c,
                1,
                cv2.LINE_AA
            )
    return overlay


# ============================================================
# Mask extraction (based on your get_linemask_v2.py + improvements)
# - 핵심 개선: "스켈레톤 전에" 마스크 연결성(브리징) 강화
# ============================================================
def threshold_base_mask(
    tophat_u8: np.ndarray,
    method: str = "adaptive",
    adaptive_block: int = 31,
    adaptive_c: int = -3,
    percentile: float = 88.0,
    roi_y0_ratio: float = 0.35,
):
    h, w = tophat_u8.shape[:2]
    method = method.lower()

    if method == "adaptive":
        block = ensure_odd_positive(adaptive_block, minimum=3)
        base = cv2.adaptiveThreshold(
            tophat_u8, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block,
            adaptive_c
        )
        return base

    if method == "otsu":
        _, base = cv2.threshold(tophat_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return base

    if method == "otsu_roi":
        y0 = int(h * roi_y0_ratio)
        y0 = np.clip(y0, 0, h - 1)
        roi = tophat_u8[y0:, :]
        _, roi_bin = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        base = np.zeros_like(tophat_u8, dtype=np.uint8)
        base[y0:, :] = roi_bin
        return base

    if method == "percentile":
        vals = tophat_u8[tophat_u8 > 0]
        if vals.size == 0:
            return np.zeros_like(tophat_u8, dtype=np.uint8)
        t = np.percentile(vals, percentile)
        base = (tophat_u8 >= t).astype(np.uint8) * 255
        return base

    raise ValueError(f"Unknown threshold method: {method} (use adaptive/otsu/otsu_roi/percentile)")


def connectivity_bridge(
    mask_u8: np.ndarray,
    pre_dilate_iter: int = 0,
    use_dir_close: bool = True,
    bridge_h: int = 21,
    bridge_v: int = 21,
    dir_close_iter: int = 1,
    final_close_k: int = 3,
    final_close_iter: int = 1,
    support_dilate_k: int = 5,      # ✅ NEW: 원본 주변 support 범위
    debug=None,
):
    if debug is None:
        debug = {}

    m0 = (mask_u8 > 0).astype(np.uint8) * 255
    debug["16_bridge_input"] = m0

    # (선택) 아주 약한 팽창
    m = m0.copy()
    if pre_dilate_iter > 0:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        m = cv2.dilate(m, k, iterations=pre_dilate_iter)
        debug["16a_pre_dilate"] = m

    # ✅ support: "원본 라인 주변"만 허용(면 채움 방지용)
    sd = max(3, int(support_dilate_k))
    if sd % 2 == 0:
        sd += 1
    ksup = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sd, sd))
    support = cv2.dilate(m0, ksup, iterations=1)
    debug["16_support_region"] = support

    if use_dir_close:
        bh = max(int(bridge_h), 5)
        bv = max(int(bridge_v), 5)
        kH = cv2.getStructuringElement(cv2.MORPH_RECT, (bh, 1))
        kV = cv2.getStructuringElement(cv2.MORPH_RECT, (1, bv))

        mh = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kH, iterations=max(int(dir_close_iter), 1))
        mv = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kV, iterations=max(int(dir_close_iter), 1))
        debug["16b_close_h"] = mh
        debug["16c_close_v"] = mv

        m_dir = cv2.bitwise_or(mh, mv)
        debug["16d_dir_close_or_raw"] = m_dir

        # ✅ 핵심: 방향성 close 결과를 support 안으로 제한
        m = cv2.bitwise_and(m_dir, support)
        debug["16d_dir_close_or_clipped"] = m

    fk = max(3, int(final_close_k))
    if fk % 2 == 0:
        fk += 1
    kF = cv2.getStructuringElement(cv2.MORPH_RECT, (fk, fk))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kF, iterations=max(int(final_close_iter), 1))
    debug["16e_final_close"] = m

    return m, debug


def extract_white_line_mask(
    bgr: np.ndarray,

    # white-ish mask thresholds
    s_th: int = 90,
    v_th: int = 150,

    # tophat
    k_tophat: int = 21,
    use_auto_tophat: bool = False,
    k_tophat_min: int = 15,

    # base thresholding
    th_method: str = "adaptive",
    adaptive_block: int = 31,
    adaptive_c: int = -3,
    percentile: float = 88.0,
    roi_y0_ratio: float = 0.35,

    # horizontal enhancement
    use_horizontal_enhance: bool = True,
    h_kernel: int = 31,
    h_thresh_method: str = "otsu",
    h_percentile: float = 90.0,

    # combine logic
    strong_percentile: float = 95.0,

    # morphology (light)
    k_close: int = 3,
    close_iter: int = 1,
    use_open: bool = False,
    k_open: int = 3,
    open_iter: int = 1,

    # smoothing
    use_median: bool = True,
    median_ksize: int = 3,

    # CC filtering (완화)
    cc_area_min: int = 12,
    cc_aspect_min: float = 1.8,
    cc_area_big: int = 250,      # 크게 잡힌 덩어리는 aspect가 낮아도 유지

    # NEW: connectivity bridging BEFORE thinning
    do_bridge: bool = True,
    pre_dilate_iter: int = 0,
    use_dir_close: bool = True,
    bridge_h: int = 31,
    bridge_v: int = 31,
    dir_close_iter: int = 1,
    final_close_k: int = 3,
    final_close_iter: int = 1,
):
    """
    Returns:
      final_mask_for_lines (uint8 0/255),
      debug_images: dict[str, np.ndarray]
    """
    h, w = bgr.shape[:2]
    debug = {}

    # 1) Color spaces
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(hsv)

    debug["01_H"] = H
    debug["02_S"] = S
    debug["03_V"] = V

    # 2) White-ish candidate in HSV
    white_hsv = ((S < s_th) & (V > v_th)).astype(np.uint8) * 255
    debug["10_white_hsv_mask"] = white_hsv

    # 3) Top-hat on V
    if use_auto_tophat:
        k = max(int(k_tophat_min), (min(h, w) // 60) * 2 + 1)
        k = ensure_odd_positive(k, minimum=3)
    else:
        k = ensure_odd_positive(k_tophat, minimum=3)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    tophat = cv2.morphologyEx(V, cv2.MORPH_TOPHAT, kernel)
    tophat_u8 = cv2.normalize(tophat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    debug["11_tophat_V_norm"] = tophat_u8

    # 4) Base threshold mask
    base = threshold_base_mask(
        tophat_u8,
        method=th_method,
        adaptive_block=adaptive_block,
        adaptive_c=adaptive_c,
        percentile=percentile,
        roi_y0_ratio=roi_y0_ratio,
    )
    debug["12_base_threshold_mask"] = base

    # 4.1) Horizontal enhancement
    if use_horizontal_enhance:
        hk = max(int(h_kernel), 3)
        hker = cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1))
        h_enh = cv2.morphologyEx(tophat_u8, cv2.MORPH_OPEN, hker)
        debug["12a_horizontal_enh"] = h_enh

        if h_thresh_method.lower() == "otsu":
            _, h_bin = cv2.threshold(h_enh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            vals = h_enh[h_enh > 0]
            if vals.size == 0:
                h_bin = np.zeros_like(h_enh, dtype=np.uint8)
            else:
                t = np.percentile(vals, h_percentile)
                h_bin = (h_enh >= t).astype(np.uint8) * 255

        debug["12b_horizontal_bin"] = h_bin
        base = cv2.bitwise_or(base, h_bin)
        debug["12c_base_plus_horizontal"] = base

    # 5) Combine WITHOUT killing faint lines
    vals = tophat_u8[tophat_u8 > 0]
    if vals.size == 0:
        strong_mask = np.zeros_like(tophat_u8, dtype=np.uint8)
    else:
        t_strong = np.percentile(vals, strong_percentile)
        strong_mask = (tophat_u8 >= t_strong).astype(np.uint8) * 255
    debug["13a_strong_tophat_mask"] = strong_mask

    keep_mask = cv2.bitwise_or(white_hsv, strong_mask)
    combined = cv2.bitwise_and(base, keep_mask)
    debug["13_combined_mask_raw"] = combined

    # 6) Light morphology (너무 공격적인 OPEN은 기본 off)
    k_close = ensure_odd_positive(k_close, minimum=3)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (k_close, k_close))
    cleaned = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close, iterations=max(int(close_iter), 1))
    debug["14a_mask_close_only"] = cleaned

    if use_open:
        k_open = ensure_odd_positive(k_open, minimum=3)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (k_open, k_open))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel_open, iterations=max(int(open_iter), 1))
        debug["14b_mask_open_applied"] = cleaned

    if use_median:
        median_ksize = ensure_odd_positive(median_ksize, minimum=3)
        cleaned = cv2.medianBlur(cleaned, median_ksize)
        debug["14c_mask_median"] = cleaned

    debug["14_mask_morph_clean"] = cleaned

    # 7) CC filtering (완화 버전: 중요한 작은 라인 조각 보존)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    filtered = np.zeros_like(cleaned)

    cc_area_min = max(int(cc_area_min), 1)
    cc_aspect_min = float(cc_aspect_min)
    cc_area_big = max(int(cc_area_big), cc_area_min)

    for i in range(1, num):
        x, y, ww, hh, area = stats[i]
        if area < cc_area_min:
            continue
        ar = max(ww, hh) / max(1, min(ww, hh))
        # 길쭉한 라인 조각은 유지, 또는 충분히 큰 덩어리도 유지(서비스라인 끊김 방지)
        if ar >= cc_aspect_min or area >= cc_area_big:
            filtered[labels == i] = 255

    debug["15_mask_cc_filtered_soft"] = filtered

    # 8) NEW: connectivity bridging BEFORE thinning
    if do_bridge:
        bridged, debug = connectivity_bridge(
            filtered,
            pre_dilate_iter=pre_dilate_iter,
            use_dir_close=use_dir_close,
            bridge_h=bridge_h,
            bridge_v=bridge_v,
            dir_close_iter=dir_close_iter,
            final_close_k=final_close_k,
            final_close_iter=final_close_iter,
            debug=debug,
        )
        final_mask = bridged
    else:
        final_mask = filtered

    # overlay
    overlay = bgr.copy()
    overlay[final_mask > 0] = (0, 0, 255)
    debug["20_overlay_red_lines"] = cv2.addWeighted(bgr, 0.45, overlay, 0.55, 0)

    return final_mask, debug

def largest_cc(mask_u8: np.ndarray) -> np.ndarray:
    m = (mask_u8 > 0).astype(np.uint8) * 255
    num, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if num <= 1:
        return m
    areas = stats[1:, cv2.CC_STAT_AREA]
    idx = int(1 + np.argmax(areas))
    out = np.zeros_like(m)
    out[labels == idx] = 255
    return out


def make_court_roi(mask_u8: np.ndarray, top_cut_px: int = 30, dilate_k: int = 9) -> np.ndarray:
    """
    mask_u8 -> court ROI (largest CC) -> (optional) remove upper band -> (optional) dilate a bit
    """
    roi = largest_cc(mask_u8)

    # 상단 컷: 네트 위/관중석 쪽 수평 노이즈 줄이기
    if top_cut_px > 0:
        ys = np.where(roi > 0)[0]
        if len(ys) > 0:
            y_top = int(np.min(ys))
            y_cut = min(roi.shape[0], y_top + int(top_cut_px))
            roi[:y_cut, :] = 0

    # 약간 확장: 라인이 ROI에 더 잘 걸리게
    if dilate_k > 0:
        if dilate_k % 2 == 0:
            dilate_k += 1
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_k, dilate_k))
        roi = cv2.dilate(roi, k, iterations=1)

    return roi


def filter_segments_by_mask_overlap(
    segs,
    mask_u8: np.ndarray,
    thickness: int = 5,
    min_overlap: float = 0.45,
    require_midpoint_in_roi: bool = True,
):
    """
    각 seg를 thickness로 그렸을 때 ROI(mask_u8)와 겹치는 비율이 min_overlap 이상인 seg만 유지.
    추가로 seg 중점이 ROI 안에 있어야 통과(require_midpoint_in_roi).
    """
    h, w = mask_u8.shape[:2]
    roi = (mask_u8 > 0).astype(np.uint8)

    kept = []
    for (x1, y1, x2, y2) in segs:
        # midpoint 조건
        if require_midpoint_in_roi:
            mx = int(round((x1 + x2) * 0.5))
            my = int(round((y1 + y2) * 0.5))
            if not (0 <= mx < w and 0 <= my < h and roi[my, mx] > 0):
                continue

        canvas = np.zeros((h, w), np.uint8)
        cv2.line(canvas, (int(x1), int(y1)), (int(x2), int(y2)), 1, thickness, cv2.LINE_AA)

        total = int(canvas.sum())
        if total <= 0:
            continue

        overlap = int((canvas & roi).sum())
        score = overlap / (total + 1e-6)

        if score >= float(min_overlap):
            kept.append([int(x1), int(y1), int(x2), int(y2)])

    return kept



def line_roi_overlap_score(p1, p2, roi_u8: np.ndarray, thickness: int = 9) -> float:
    """
    (p1,p2) 직선을 두껍게 그렸을 때 ROI와 겹치는 비율
    """
    h, w = roi_u8.shape[:2]
    roi = (roi_u8 > 0).astype(np.uint8)

    canvas = np.zeros((h, w), np.uint8)
    cv2.line(canvas, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), 1, thickness, cv2.LINE_AA)

    total = int(canvas.sum())
    if total <= 0:
        return 0.0

    overlap = int((canvas & roi).sum())
    return overlap / (total + 1e-6)


def filter_fitted_lines_by_roi(fitted_lines, roi_u8: np.ndarray, min_score: float = 0.25, thickness: int = 9):
    """
    fitted_lines: [{"p1":(x,y), "p2":(x,y), ...}, ...] 형태를 가정
    """
    out = []
    for L in fitted_lines:
        s = line_roi_overlap_score(L["p1"], L["p2"], roi_u8, thickness=thickness)
        if s >= float(min_score):
            L = dict(L)
            L["roi_score"] = float(s)
            out.append(L)
    return out



# ============================================================
# Thinning (Zhang-Suen) - no opencv-contrib dependency
# ============================================================
def zhang_suen_thinning(bin_img: np.ndarray, max_iter: int = 100) -> np.ndarray:
    img = (bin_img > 0).astype(np.uint8)
    h, w = img.shape[:2]

    def neighbors(x, y):
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


# ============================================================
# Line detection pipeline (skeleton -> Hough segments -> clustering -> parallel lines -> labels)
# ============================================================
def segments_from_hough(skel: np.ndarray, min_len=40, max_gap=25, thresh=40):
    lines = cv2.HoughLinesP(skel, 1, np.pi/180, threshold=int(thresh),
                            minLineLength=int(min_len), maxLineGap=int(max_gap))
    segs = []
    if lines is not None:
        for l in lines[:, 0, :]:
            segs.append(l.astype(int).tolist())
    return segs


def segment_angle_deg(seg):
    x1,y1,x2,y2 = seg
    dx = x2 - x1
    dy = y2 - y1
    ang = math.degrees(math.atan2(dy, dx))
    ang = ang % 180.0
    return ang


def kmeans_two_angle_clusters(segs):
    if len(segs) == 0:
        return [], []

    feats = []
    for s in segs:
        th = math.radians(segment_angle_deg(s))
        feats.append([math.cos(2*th), math.sin(2*th)])
    feats = np.array(feats, dtype=np.float32)

    if len(segs) < 4:
        return [0]*len(segs), [segment_angle_deg(segs[0]), segment_angle_deg(segs[0])]

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3)
    _, labels, centers = cv2.kmeans(feats, 2, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    labels = labels.flatten().tolist()

    mean_angles = []
    for c in centers:
        two = math.atan2(float(c[1]), float(c[0]))
        th = two / 2.0
        ang = (math.degrees(th) % 180.0)
        mean_angles.append(ang)

    def ang_dist_180(a, b):
            # both in degrees, modulo 180
            a = a % 180.0
            b = b % 180.0
            d = abs(a - b)
            return min(d, 180.0 - d)

    # --- after computing labels and mean_angles ---
    # decide which cluster is "horizontal-like" (closer to 0 deg)
    h_idx = 0 if ang_dist_180(mean_angles[0], 0.0) <= ang_dist_180(mean_angles[1], 0.0) else 1
    v_idx = 1 - h_idx

    # remap labels so: 0 = horizontal cluster, 1 = vertical cluster
    remap = {h_idx: 0, v_idx: 1}
    labels = [remap[l] for l in labels]
    mean_angles = [mean_angles[h_idx], mean_angles[v_idx]]
    print("[05] mean_angles:", mean_angles)

    return labels, mean_angles


def draw_segments_overlay(img_bgr, segs, labels=None, colors=None, alpha=0.8):
    base = img_bgr.copy()
    overlay = img_bgr.copy()
    for i, s in enumerate(segs):
        x1,y1,x2,y2 = s
        if labels is None or colors is None:
            col = (0,255,0)
        else:
            col = colors[labels[i] % len(colors)]
        cv2.line(overlay, (x1,y1), (x2,y2), col, 2, cv2.LINE_AA)
    return cv2.addWeighted(overlay, alpha, base, 1-alpha, 0)


def compute_rho_for_segments(segs, theta_line_rad):
    nx = -math.sin(theta_line_rad)
    ny =  math.cos(theta_line_rad)
    rhos = []
    for s in segs:
        x1,y1,x2,y2 = s
        mx = 0.5*(x1+x2)
        my = 0.5*(y1+y2)
        rho = mx*nx + my*ny
        rhos.append(rho)
    return np.array(rhos, dtype=np.float32)


def smooth_1d(arr, k=9):
    k = max(3, int(k))
    if k % 2 == 0:
        k += 1
    ker = np.ones(k, dtype=np.float32) / k
    return np.convolve(arr, ker, mode="same")


def find_peaks_1d(y, min_prom=0.20, min_dist=10):
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

    filtered = []
    for p in peaks:
        if not filtered:
            filtered.append(p)
        else:
            if all(abs(p - q) >= min_dist for q in filtered):
                filtered.append(p)
    return filtered


def fit_line_tls(points_xy):
    pts = np.asarray(points_xy, dtype=np.float32)
    if len(pts) < 2:
        return None
    c = pts.mean(axis=0)
    X = pts - c
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    direction = vt[0]
    dx, dy = float(direction[0]), float(direction[1])
    a = -dy
    b = dx
    norm = math.hypot(a, b) + 1e-9
    a /= norm
    b /= norm
    c0 = -(a*c[0] + b*c[1])
    return (a, b, c0)


def line_intersections_with_image(a, b, c, w, h):
    pts = []
    if abs(b) > 1e-9:
        y = -(c) / b
        if 0 <= y <= h-1:
            pts.append((0, int(round(y))))
        y = -(a*(w-1) + c) / b
        if 0 <= y <= h-1:
            pts.append((w-1, int(round(y))))
    if abs(a) > 1e-9:
        x = -(c) / a
        if 0 <= x <= w-1:
            pts.append((int(round(x)), 0))
        x = -(b*(h-1) + c) / a
        if 0 <= x <= w-1:
            pts.append((int(round(x)), h-1))

    uniq = []
    for p in pts:
        if p not in uniq:
            uniq.append(p)
    if len(uniq) <= 2:
        return uniq
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


def rho_hist_image(rhos, bins=140, width=900, height=220, peaks=None, title="rho_hist"):
    img = np.zeros((height, width, 3), np.uint8)
    if rhos is None or rhos.size == 0:
        cv2.putText(img, "No rhos", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2, cv2.LINE_AA)
        cv2.putText(img, title, (40, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
        return img

    hist, edges = np.histogram(rhos, bins=bins)
    hist = hist.astype(np.float32)
    hist_s = smooth_1d(hist, k=9)
    hist_s = hist_s / (hist_s.max() + 1e-6)

    cv2.line(img, (40, height-30), (width-20, height-30), (200,200,200), 1)
    cv2.line(img, (40, 20), (40, height-30), (200,200,200), 1)

    x0, x1 = 40, width-20
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
    rho_tol=16.0,
    max_lines=8,
    peak_min_prom=0.20,
    peak_min_dist=10
):
    if len(segs) == 0:
        return [], None, None

    theta = math.radians(mean_angle_deg)
    rhos = compute_rho_for_segments(segs, theta)

    hist, edges = np.histogram(rhos, bins=int(peak_bins))
    hist_s = smooth_1d(hist.astype(np.float32), k=9)
    peaks_idx = find_peaks_1d(hist_s, min_prom=float(peak_min_prom), min_dist=int(peak_min_dist))

    peaks_idx = sorted(peaks_idx, key=lambda i: float(hist_s[i]), reverse=True)[:int(max_lines)]
    peaks_idx = sorted(peaks_idx)

    peak_rhos = []
    for pi in peaks_idx:
        r0 = 0.5*(edges[pi] + edges[pi+1])
        peak_rhos.append(float(r0))

    fitted = []
    for r0 in peak_rhos:
        pts = []
        nx = -math.sin(theta)
        ny =  math.cos(theta)
        for s in segs:
            x1,y1,x2,y2 = s
            mx = 0.5*(x1+x2)
            my = 0.5*(y1+y2)
            rho = mx*nx + my*ny
            if abs(rho - r0) <= float(rho_tol):
                pts.append((x1,y1))
                pts.append((x2,y2))

        line = fit_line_tls(pts)
        if line is None:
            continue
        a,b,c = line
        pts2 = line_intersections_with_image(a,b,c,w,h)
        if len(pts2) == 2:
            fitted.append({"abc": (a,b,c), "p1": pts2[0], "p2": pts2[1], "rho": r0})

    fitted = sorted(fitted, key=lambda d: d["rho"])
    dedup = []
    for L in fitted:
        if not dedup:
            dedup.append(L)
        else:
            if abs(L["rho"] - dedup[-1]["rho"]) > (float(rho_tol) * 0.8):
                dedup.append(L)

    return dedup, rhos, peaks_idx


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

    if n >= 5:
        names = ["doubles_sideline_L", "singles_sideline_L", "center_line",
                 "singles_sideline_R", "doubles_sideline_R"]
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
        labeled.append(("doubles_sideline_L", xs[0][1]))
        if n > 2:
            labeled.append(("center_line", xs[n//2][1]))
        labeled.append(("doubles_sideline_R", xs[-1][1]))

    return labeled


def label_crosswise_lines(lines, w, h):
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
        for i, (_, L) in enumerate(ys):
            labeled.append((f"cross_line_{i}", L))

    return labeled


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


def draw_labeled_lines(img_bgr, labeled_lines, thickness=4):
    out = img_bgr.copy()
    cmap = color_map_bgr()
    for name, L in labeled_lines:
        col = cmap.get(name, (200, 200, 200))
        p1, p2 = L["p1"], L["p2"]
        cv2.line(out, p1, p2, col, int(thickness), cv2.LINE_AA)
        lx = int(p1[0] + 8)
        ly = int(p1[1] - 8)
        put_label(out, name, lx, max(20, ly), col)
    return out

# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input image (BGR)")
    parser.add_argument("--out_root", default="results_full", help="Output root folder name under CWD")
    parser.add_argument("--zip", action="store_true", help="Zip output images")

    # --- Mask params (same spirit as your v2 + new bridging knobs)
    parser.add_argument("--s_th", type=int, default=90)
    parser.add_argument("--v_th", type=int, default=150)

    parser.add_argument("--k_tophat", type=int, default=21)
    parser.add_argument("--use_auto_tophat", action="store_true")
    parser.add_argument("--k_tophat_min", type=int, default=15)

    parser.add_argument("--th_method", type=str, default="adaptive",
                        choices=["adaptive", "otsu", "otsu_roi", "percentile"])
    parser.add_argument("--adaptive_block", type=int, default=31)
    parser.add_argument("--adaptive_c", type=int, default=-3)
    parser.add_argument("--percentile", type=float, default=88.0)
    parser.add_argument("--roi_y0_ratio", type=float, default=0.35)

    parser.add_argument("--no_horizontal_enhance", action="store_true")
    parser.add_argument("--h_kernel", type=int, default=31)
    parser.add_argument("--h_thresh_method", type=str, default="otsu", choices=["otsu", "percentile"])
    parser.add_argument("--h_percentile", type=float, default=90.0)

    parser.add_argument("--strong_percentile", type=float, default=95.0)

    parser.add_argument("--k_close", type=int, default=3)
    parser.add_argument("--close_iter", type=int, default=1)
    parser.add_argument("--use_open", action="store_true")
    parser.add_argument("--k_open", type=int, default=3)
    parser.add_argument("--open_iter", type=int, default=1)

    parser.add_argument("--no_median", action="store_true")
    parser.add_argument("--median_ksize", type=int, default=3)

    parser.add_argument("--cc_area_min", type=int, default=12)
    parser.add_argument("--cc_aspect_min", type=float, default=1.8)
    parser.add_argument("--cc_area_big", type=int, default=250)

    # bridging
    parser.add_argument("--no_bridge", action="store_true")
    parser.add_argument("--pre_dilate_iter", type=int, default=0)   # 0~1 추천
    parser.add_argument("--no_dir_close", action="store_true")
    parser.add_argument("--bridge_h", type=int, default=31)
    parser.add_argument("--bridge_v", type=int, default=31)
    parser.add_argument("--dir_close_iter", type=int, default=1)
    parser.add_argument("--final_close_k", type=int, default=3)
    parser.add_argument("--final_close_iter", type=int, default=1)

    # --- Thinning & Hough params
    parser.add_argument("--thin_iter", type=int, default=80)
    parser.add_argument("--hough_thresh", type=int, default=40)
    parser.add_argument("--min_len", type=int, default=40)
    parser.add_argument("--max_gap", type=int, default=25)

    # --- rho peak params
    parser.add_argument("--peak_bins", type=int, default=140)
    parser.add_argument("--rho_tol", type=float, default=16.0)
    parser.add_argument("--max_lines_each", type=int, default=8)
    parser.add_argument("--peak_min_prom", type=float, default=0.20)
    parser.add_argument("--peak_min_dist", type=int, default=10)

    parser.add_argument("--horiz_thr", type=float, default=20.0, help="Signed-angle threshold (deg) for horizontal cluster")



    args = parser.parse_args()

    bgr = cv2.imread(args.input)
    if bgr is None:
        raise FileNotFoundError(f"Failed to read image: {args.input}")

    out_dir = make_out_dir(args.out_root)
    print(f"[INFO] Output dir: {out_dir}")

    save_png(out_dir, "00_original", bgr)

    # 1) Mask extraction + debug saves
    mask, debug_mask = extract_white_line_mask(
        bgr,
        s_th=args.s_th,
        v_th=args.v_th,
        k_tophat=args.k_tophat,
        use_auto_tophat=args.use_auto_tophat,
        k_tophat_min=args.k_tophat_min,
        th_method=args.th_method,
        adaptive_block=args.adaptive_block,
        adaptive_c=args.adaptive_c,
        percentile=args.percentile,
        roi_y0_ratio=args.roi_y0_ratio,
        use_horizontal_enhance=(not args.no_horizontal_enhance),
        h_kernel=args.h_kernel,
        h_thresh_method=args.h_thresh_method,
        h_percentile=args.h_percentile,
        strong_percentile=args.strong_percentile,
        k_close=args.k_close,
        close_iter=args.close_iter,
        use_open=args.use_open,
        k_open=args.k_open,
        open_iter=args.open_iter,
        use_median=(not args.no_median),
        median_ksize=args.median_ksize,
        cc_area_min=args.cc_area_min,
        cc_aspect_min=args.cc_aspect_min,
        cc_area_big=args.cc_area_big,
        do_bridge=(not args.no_bridge),
        pre_dilate_iter=args.pre_dilate_iter,
        use_dir_close=(not args.no_dir_close),
        bridge_h=args.bridge_h,
        bridge_v=args.bridge_v,
        dir_close_iter=args.dir_close_iter,
        final_close_k=args.final_close_k,
        final_close_iter=args.final_close_iter,
    )

    for name, im in debug_mask.items():
        save_png(out_dir, f"01_mask_{name}", im)
    save_png(out_dir, "02_final_mask_for_lines", mask)

    # 02b) ROI gate from 02 (largest CC + optional top cut + dilate)
    # court_roi = make_court_roi(mask, top_cut_px=30, dilate_k=9)
    court_roi = make_court_roi(mask, top_cut_px=0, dilate_k=9)
    save_png(out_dir, "02b_court_roi_largestcc_topcut", court_roi)

    # 03) Focused mask = precise mask (02) AND ROI gate (02b)
    mask_focus = cv2.bitwise_and(mask, court_roi)
    save_png(out_dir, "03_0_mask_focus_02_and_roi", mask_focus)

    # 2) Thinning -> skeleton
    skel = zhang_suen_thinning(mask_focus, max_iter=args.thin_iter)

    thick_for_hough = mask_focus.copy()
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thick_for_hough = cv2.morphologyEx(thick_for_hough, cv2.MORPH_CLOSE, k, iterations=1)
    save_png(out_dir, "03_1_thick_for_hough", thick_for_hough)

    # 2.6) Remove thick blobs -> keep only thin line-like pixels for Hough
    # dist: foreground(255) 내부에서 배경(0)까지의 거리 (대략 "두께" 지표)
    dist = cv2.distanceTransform((thick_for_hough > 0).astype(np.uint8), cv2.DIST_L2, 3)

    # <= 2.2 정도면 대략 1~4px 폭의 선 성분만 남는 느낌 (이미지에 따라 1.8~3.0 튜닝)
    dt_th = getattr(args, "dt_th", 2.0)
    thin_for_hough = (dist <= dt_th).astype(np.uint8) * 255

    # 약간 정리
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thin_for_hough = cv2.morphologyEx(thin_for_hough, cv2.MORPH_OPEN, k3, iterations=1)

    save_png(out_dir, "03_2_thin_for_hough_dt", thin_for_hough)

    # Hough는 "엣지"에 주는 게 더 안정적
    edges_for_hough = cv2.Canny(thin_for_hough, 50, 150)
    save_png(out_dir, "03_3_edges_for_hough", edges_for_hough)

    # 3) Hough segments
    segs = segments_from_hough(
        edges_for_hough,
        min_len=args.min_len,
        max_gap=args.max_gap,
        thresh=args.hough_thresh
    )

    save_png(out_dir, "04_segments_before_roi_filter", draw_segments_overlay(bgr, segs))

    segs = filter_segments_by_mask_overlap(
        segs,
        court_roi,
        thickness=7,
        min_overlap=0.30,
        require_midpoint_in_roi=False,
    )

    save_png(out_dir, "04b_segments_after_roi_filter", draw_segments_overlay(bgr, segs))



    def get_p1p2(s):
        """
        Accepts segment in multiple formats and returns:
        p1=(x1,y1), p2=(x2,y2) as int tuples.
        Supported:
        - dict: {"p1":(x1,y1), "p2":(x2,y2)}
        - list/tuple: [x1,y1,x2,y2] or ((x1,y1),(x2,y2))
        - np.ndarray: [x1,y1,x2,y2] or [[x1,y1,x2,y2]]
        """
        # dict case
        if isinstance(s, dict):
            p1 = s.get("p1", None)
            p2 = s.get("p2", None)
            if p1 is None or p2 is None:
                raise ValueError(f"dict seg missing p1/p2 keys: {s.keys()}")
            return (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))

        # numpy case
        if isinstance(s, np.ndarray):
            a = s.reshape(-1).tolist()
            if len(a) < 4:
                raise ValueError(f"ndarray seg shape unexpected: {s.shape}")
            x1,y1,x2,y2 = a[:4]
            return (int(x1), int(y1)), (int(x2), int(y2))

        # list/tuple case
        if isinstance(s, (list, tuple)):
            # ((x1,y1),(x2,y2))
            if len(s) == 2 and isinstance(s[0], (list, tuple)) and isinstance(s[1], (list, tuple)):
                x1,y1 = s[0]
                x2,y2 = s[1]
                return (int(x1), int(y1)), (int(x2), int(y2))

            # [x1,y1,x2,y2]
            if len(s) >= 4 and all(isinstance(v, (int, float, np.integer, np.floating)) for v in s[:4]):
                x1,y1,x2,y2 = s[:4]
                return (int(x1), int(y1)), (int(x2), int(y2))

        raise TypeError(f"Unsupported segment type: {type(s)} / value={s}")

    def seg_mid(s):
        (x1,y1),(x2,y2) = get_p1p2(s)
        return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)

    def seg_len(s):
        (x1,y1),(x2,y2) = get_p1p2(s)
        dx = x2 - x1
        dy = y2 - y1
        return math.hypot(dx, dy), dx, dy

    def angle_deg_0_180(s):
        (x1,y1),(x2,y2) = get_p1p2(s)
        dx = x2 - x1
        dy = y2 - y1
        return (math.degrees(math.atan2(dy, dx)) % 180.0)

    def save_segments_csv(path, segs, labels=None, roi_overlap=None, W=None, H=None):
        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow([
                "idx","x1","y1","x2","y2","dx","dy","len","angle_deg",
                "label","mid_x","mid_y","roi_overlap","norm_x","norm_y"
            ])
            for i, s in enumerate(segs):
                (x1,y1),(x2,y2) = get_p1p2(s)
                L, dx, dy = seg_len(s)
                ang = angle_deg_0_180(s)
                mx, my = seg_mid(s)
                lab = labels[i] if labels is not None and i < len(labels) else -1
                ov  = roi_overlap[i] if roi_overlap is not None and i < len(roi_overlap) else -1
                nx = (mx / max(1, W)) if W else -1
                ny = (my / max(1, H)) if H else -1
                wr.writerow([i,x1,y1,x2,y2,dx,dy,L,ang,lab,mx,my,ov,nx,ny])


    # 4) Angle clustering (3-way, signed)
    seg_labels, ang_stats = cluster_segments_3way_signed(segs, horiz_thr_deg=args.horiz_thr)

    # 3클러스터 색상(가로/우사선/좌사선)
    cluster_colors = [
        (0, 255, 0),   # label 0: horizontal-ish
        (0, 0, 255),   # label 1: +slope
        (255, 0, 0),   # label 2: -slope
    ]

    # 기존 overlay가 alpha 지원하는 draw_segments_overlay를 쓰고 싶으면, 네 기존 함수를 그대로 써도 됨
    seg_cluster_overlay = draw_segments_overlay(bgr, segs, labels=seg_labels, colors=cluster_colors, alpha=0.80)
    save_png(out_dir, "05_segments_angle_clusters_3way", seg_cluster_overlay)

    # 각도 텍스트까지 찍는 디버그 오버레이
    save_png(out_dir, "05b_segments_angle_text", draw_segments_overlay_with_angle_text(bgr, segs, labels=seg_labels, colors=cluster_colors, topN=80))

    # CSV 저장(원인 분석 핵심)
    H, W = bgr.shape[:2]
    save_segments_csv(out_dir/"05_segments_debug.csv", segs, labels=seg_labels, W=W, H=H)

    print(f"[05] angle stats: {ang_stats}")

    # 05 단계 이후: 3-way cluster 유효성 체크
    cnt_h = sum(1 for lb in seg_labels if lb == 0)  # horizontal
    cnt_p = sum(1 for lb in seg_labels if lb == 1)  # +slope
    cnt_n = sum(1 for lb in seg_labels if lb == 2)  # -slope

    # 최소 기준(원하면 튜닝): 가로선은 충분, 사선은 각각 최소 3개 정도
    min_h = getattr(args, "min_segs_horiz", 8)
    min_d = getattr(args, "min_segs_diag", 3)

    if (cnt_h < min_h) or (cnt_p < min_d) or (cnt_n < min_d):
        final = bgr.copy()
        put_label(final, f"Not enough segments: H={cnt_h}, +={cnt_p}, -={cnt_n}", 30, 40, (0,0,255))
        save_png(out_dir, "99_final_labeled_lines", final)
        print(f"[WARN] Not enough segments for 3-way clustering: H={cnt_h}, +={cnt_p}, -={cnt_n}")
        return

    segs0 = [s for s, lb in zip(segs, seg_labels) if lb == 0]
    segs1 = [s for s, lb in zip(segs, seg_labels) if lb == 1]

    h, w = bgr.shape[:2]

    # 5) Parallel lines per cluster via rho peaks
    lines0, rhos0, peaks0 = extract_parallel_lines_from_cluster(
        segs0, mean_angles[0], w, h,
        peak_bins=args.peak_bins,
        rho_tol=args.rho_tol,
        max_lines=args.max_lines_each,
        peak_min_prom=args.peak_min_prom,
        peak_min_dist=args.peak_min_dist
    )
    lines1, rhos1, peaks1 = extract_parallel_lines_from_cluster(
        segs1, mean_angles[1], w, h,
        peak_bins=args.peak_bins,
        rho_tol=args.rho_tol,
        max_lines=args.max_lines_each,
        peak_min_prom=args.peak_min_prom,
        peak_min_dist=args.peak_min_dist
    )

    save_png(out_dir, "06_rho_hist_cluster0", rho_hist_image(rhos0, bins=args.peak_bins, peaks=peaks0, title="rho_hist_cluster0"))
    save_png(out_dir, "07_rho_hist_cluster1", rho_hist_image(rhos1, bins=args.peak_bins, peaks=peaks1, title="rho_hist_cluster1"))

    # ----------------------------
    # 08) parallel lines by cluster (DEBUG: before / after ROI filtering)
    # ----------------------------

    # (1) 필터 전 오버레이 저장
    raw_before = bgr.copy()
    for L in lines0:
        cv2.line(raw_before, L["p1"], L["p2"], (0, 255, 0), 2, cv2.LINE_AA)  # cluster0=green
    for L in lines1:
        cv2.line(raw_before, L["p1"], L["p2"], (0, 0, 255), 2, cv2.LINE_AA)  # cluster1=red

    save_png(out_dir, "08a_parallel_lines_by_cluster_RAW", raw_before)

    # (2) ✅ 여기서 ROI 필터 적용 (클러스터별로!)
    lines0 = filter_fitted_lines_by_roi(lines0, court_roi, min_score=0.25, thickness=9)
    lines1 = filter_fitted_lines_by_roi(lines1, court_roi, min_score=0.25, thickness=9)

    # (3) 필터 후 오버레이 저장
    raw_after = bgr.copy()
    for L in lines0:
        cv2.line(raw_after, L["p1"], L["p2"], (0, 255, 0), 2, cv2.LINE_AA)
    for L in lines1:
        cv2.line(raw_after, L["p1"], L["p2"], (0, 0, 255), 2, cv2.LINE_AA)

    save_png(out_dir, "08b_parallel_lines_by_cluster_ROI", raw_after)

    # 6) decide which cluster is lengthwise (more vertical)
    def vertical_score(angle_deg):
        return abs(float(angle_deg) - 90.0)

    is0_vertical = vertical_score(mean_angles[0]) < vertical_score(mean_angles[1])
    if is0_vertical:
        lengthwise = lines0
        crosswise = lines1
        len_angle, crs_angle = mean_angles[0], mean_angles[1]
    else:
        lengthwise = lines1
        crosswise = lines0
        len_angle, crs_angle = mean_angles[1], mean_angles[0]

    info = {
        "mean_angles_deg": {"cluster0": mean_angles[0], "cluster1": mean_angles[1]},
        "chosen": {"lengthwise_angle": len_angle, "crosswise_angle": crs_angle},
        "num_segments": len(segs),
        "num_lines": {"cluster0": len(lines0), "cluster1": len(lines1)},
    }
    save_json(out_dir, "09_debug_info", info)

    # 7) Label heuristics
    labeled_len = label_lengthwise_lines(lengthwise, w, h)
    labeled_crs = label_crosswise_lines(crosswise, w, h)

    img_len = draw_labeled_lines(bgr, labeled_len, thickness=3)
    save_png(out_dir, "10_labeled_lengthwise", img_len)

    img_crs = draw_labeled_lines(bgr, labeled_crs, thickness=3)
    save_png(out_dir, "11_labeled_crosswise", img_crs)

    labeled_all = labeled_len + labeled_crs
    final = draw_labeled_lines(bgr, labeled_all, thickness=4)
    save_png(out_dir, "99_final_labeled_lines", final)

    # 8) Save structured line results
    out_lines = []
    for name, L in labeled_all:
        a,b,c = L["abc"]
        out_lines.append({
            "label": name,
            "p1": {"x": int(L["p1"][0]), "y": int(L["p1"][1])},
            "p2": {"x": int(L["p2"][0]), "y": int(L["p2"][1])},
            "abc": {"a": float(a), "b": float(b), "c": float(c)},
            "rho": float(L.get("rho", 0.0)),
        })
    save_json(out_dir, "99_lines_labeled", out_lines)

    # Zip (optional)
    if args.zip:
        zip_path = out_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out_dir.glob("*.png")):
                z.write(p, arcname=p.name)
            for p in sorted(out_dir.glob("*.json")):
                z.write(p, arcname=p.name)
        print(f"[INFO] Zipped: {zip_path}")

    print("[DONE]")


if __name__ == "__main__":
    main()


"""
python court_full_pipeline.py --input fullcourt_wide.jpg --out_root results_full \
  --pre_dilate_iter 1 \
  --bridge_h 41 --bridge_v 41 \
  --hough_thresh 35 --min_len 35 --max_gap 35


python court_full_pipeline.py --input fullcourt_wide.jpg --out_root results_full \
  --pre_dilate_iter 1 \
  --bridge_h 21 --bridge_v 21 \
  --hough_thresh 35 --min_len 25 --max_gap 70


python court_full_pipeline.py --input fullcourt_wide.jpg --out_root results_full \
  --pre_dilate_iter 1 \
  --bridge_h 21 --bridge_v 21 \
  --hough_thresh 35 --min_len 35 --max_gap 35 \
  --horiz_thr 18
"""