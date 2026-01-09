import argparse
import datetime
import uuid
from pathlib import Path
import zipfile

import cv2
import numpy as np


def make_out_dir(root: str = "results") -> Path:
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    out_dir = Path.cwd() / root / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def save_png(out_dir: Path, name: str, img: np.ndarray) -> Path:
    path = out_dir / f"{name}.png"
    cv2.imwrite(str(path), img)
    return path


def ensure_odd_positive(x: int, minimum: int = 1) -> int:
    x = max(int(x), int(minimum))
    if x % 2 == 0:
        x += 1
    return x


def threshold_base_mask(
    tophat_u8: np.ndarray,
    method: str = "adaptive",
    adaptive_block: int = 31,
    adaptive_c: int = -3,
    percentile: float = 88.0,
    roi_y0_ratio: float = 0.35,
):
    """
    Return base binary mask (uint8 0/255) from tophat response.
    """
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


def extract_white_line_mask(
    bgr: np.ndarray,

    # white-ish mask thresholds
    s_th: int = 90,
    v_th: int = 150,

    # tophat
    k_tophat: int = 21,          # 고정 커널(반코트/저각도에 안정적)
    use_auto_tophat: bool = False,
    k_tophat_min: int = 15,

    # base thresholding
    th_method: str = "adaptive",  # adaptive/otsu/otsu_roi/percentile
    adaptive_block: int = 31,
    adaptive_c: int = -3,
    percentile: float = 88.0,
    roi_y0_ratio: float = 0.35,

    # horizontal enhancement (서비스라인/베이스라인 강화)
    use_horizontal_enhance: bool = True,
    h_kernel: int = 31,        # 가로 커널 길이
    h_thresh_method: str = "otsu",  # otsu/percentile
    h_percentile: float = 90.0,

    # combine logic
    strong_percentile: float = 95.0,  # "white 실패해도 tophat strong면 살리기"용

    # morphology
    k_close: int = 3,
    close_iter: int = 1,
    use_open: bool = False,
    k_open: int = 3,
    open_iter: int = 1,

    # smoothing
    use_median: bool = True,
    median_ksize: int = 3,

    # CC filtering (line-like)
    cc_area_min: int = 20,
    cc_aspect_min: float = 2.5,
):
    """
    Returns:
      final_mask (uint8 0/255),
      debug_images: dict[str, np.ndarray]
    """
    h, w = bgr.shape[:2]
    debug = {}

    # 1) Color spaces
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    H, S, V = cv2.split(hsv)
    L, A, B = cv2.split(lab)

    debug["01_H"] = H
    debug["02_S"] = S
    debug["03_V"] = V
    debug["04_L"] = L

    # 2) White-ish candidate in HSV (low saturation, high value)
    white_hsv = ((S < s_th) & (V > v_th)).astype(np.uint8) * 255
    debug["10_white_hsv_mask"] = white_hsv

    # 3) Top-hat on V channel to emphasize thin bright lines
    if use_auto_tophat:
        k = max(int(k_tophat_min), (min(h, w) // 60) * 2 + 1)
        k = ensure_odd_positive(k, minimum=3)
    else:
        k = ensure_odd_positive(k_tophat, minimum=3)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    tophat = cv2.morphologyEx(V, cv2.MORPH_TOPHAT, kernel)
    tophat_u8 = cv2.normalize(tophat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    debug["11_tophat_V_norm"] = tophat_u8

    # 4) Base threshold mask (adaptive/otsu/otsu_roi/percentile)
    base = threshold_base_mask(
        tophat_u8,
        method=th_method,
        adaptive_block=adaptive_block,
        adaptive_c=adaptive_c,
        percentile=percentile,
        roi_y0_ratio=roi_y0_ratio,
    )
    debug["12_base_threshold_mask"] = base

    # 4.1) Horizontal enhancement (helps service/baseline)
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

    # 5) Combine with white mask WITHOUT killing faint lines:
    # keep pixel if base==1 AND (white_hsv==1 OR tophat is "strong")
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

    # 6) Morphology cleanup (close small, open optional)
    k_close = ensure_odd_positive(k_close, minimum=3)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (k_close, k_close))
    close_iter = max(int(close_iter), 1)

    cleaned = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close, iterations=close_iter)
    debug["14a_mask_close_only"] = cleaned

    if use_open:
        k_open = ensure_odd_positive(k_open, minimum=3)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (k_open, k_open))
        open_iter = max(int(open_iter), 1)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel_open, iterations=open_iter)
        debug["14b_mask_open_applied"] = cleaned

    if use_median:
        median_ksize = ensure_odd_positive(median_ksize, minimum=3)
        cleaned = cv2.medianBlur(cleaned, median_ksize)
        debug["14c_mask_median"] = cleaned

    debug["14_mask_morph_clean"] = cleaned

    # 7) Connected components filter by area + elongation
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    filtered = np.zeros_like(cleaned)

    cc_area_min = max(int(cc_area_min), 1)
    cc_aspect_min = float(cc_aspect_min)

    for i in range(1, num):
        x, y, ww, hh, area = stats[i]
        if area < cc_area_min:
            continue
        ar = max(ww, hh) / max(1, min(ww, hh))
        if ar >= cc_aspect_min:
            filtered[labels == i] = 255

    debug["15_mask_cc_filtered"] = filtered

    # 8) Overlay
    overlay = bgr.copy()
    overlay[filtered > 0] = (0, 0, 255)  # red
    blend = cv2.addWeighted(bgr, 0.45, overlay, 0.55, 0)
    debug["20_overlay_red_lines"] = blend

    return filtered, debug


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input image")
    parser.add_argument("--out_root", default="results", help="Output root folder name under CWD")
    parser.add_argument("--zip", action="store_true", help="Zip output images")

    # white-ish thresholds
    parser.add_argument("--s_th", type=int, default=90)
    parser.add_argument("--v_th", type=int, default=150)

    # tophat
    parser.add_argument("--k_tophat", type=int, default=21)
    parser.add_argument("--use_auto_tophat", action="store_true")
    parser.add_argument("--k_tophat_min", type=int, default=15)

    # threshold method
    parser.add_argument("--th_method", type=str, default="adaptive", choices=["adaptive", "otsu", "otsu_roi", "percentile"])
    parser.add_argument("--adaptive_block", type=int, default=31)
    parser.add_argument("--adaptive_c", type=int, default=-3)
    parser.add_argument("--percentile", type=float, default=88.0)
    parser.add_argument("--roi_y0_ratio", type=float, default=0.35)

    # horizontal enhance
    parser.add_argument("--no_horizontal_enhance", action="store_true")
    parser.add_argument("--h_kernel", type=int, default=31)
    parser.add_argument("--h_thresh_method", type=str, default="otsu", choices=["otsu", "percentile"])
    parser.add_argument("--h_percentile", type=float, default=90.0)

    # strong preserve
    parser.add_argument("--strong_percentile", type=float, default=95.0)

    # morphology
    parser.add_argument("--k_close", type=int, default=3)
    parser.add_argument("--close_iter", type=int, default=1)
    parser.add_argument("--use_open", action="store_true")
    parser.add_argument("--k_open", type=int, default=3)
    parser.add_argument("--open_iter", type=int, default=1)

    # smoothing
    parser.add_argument("--no_median", action="store_true")
    parser.add_argument("--median_ksize", type=int, default=3)

    # CC filter
    parser.add_argument("--cc_area_min", type=int, default=20)
    parser.add_argument("--cc_aspect_min", type=float, default=2.5)

    args = parser.parse_args()

    bgr = cv2.imread(args.input)
    if bgr is None:
        raise FileNotFoundError(f"Failed to read image: {args.input}")

    out_dir = make_out_dir(args.out_root)
    print(f"[INFO] Output dir: {out_dir}")

    save_png(out_dir, "00_original", bgr)

    final_mask, debug = extract_white_line_mask(
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
    )

    # Save debug images
    for name, im in debug.items():
        save_png(out_dir, name, im)

    # Save final
    save_png(out_dir, "99_final_white_line_mask", final_mask)

    # Zip (optional)
    if args.zip:
        zip_path = out_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out_dir.glob("*.png")):
                z.write(p, arcname=p.name)
        print(f"[INFO] Zipped: {zip_path}")

    print("[DONE]")


if __name__ == "__main__":
    main()

# python get_linemask_v2.py --input fullcourt_wide.jpg --out_root results