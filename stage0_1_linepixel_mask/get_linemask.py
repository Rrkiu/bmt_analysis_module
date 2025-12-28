import argparse
import datetime
import uuid
from pathlib import Path
import zipfile

import cv2
import numpy as np


def make_out_dir(root: str = "results") -> Path:
    """
    Create a unique output directory per run to avoid overwriting.
    Example: results/20251228_153012_a1b2c3/
    """
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    out_dir = Path.cwd() / root / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def save_png(out_dir: Path, name: str, img: np.ndarray) -> Path:
    path = out_dir / f"{name}.png"
    cv2.imwrite(str(path), img)
    return path


def _ensure_odd_positive(x: int, minimum: int = 1) -> int:
    x = max(int(x), int(minimum))
    if x % 2 == 0:
        x += 1
    return x


def extract_white_line_mask(
    bgr: np.ndarray,
    s_th: int = 70,
    v_th: int = 160,
    k_tophat_min: int = 15,
    k_close: int = 3,
    close_iter: int = 1,
    use_open: bool = False,
    k_open: int = 3,
    open_iter: int = 1,
    use_median: bool = True,
    median_ksize: int = 3,
    cc_area_min: int = 30,
    cc_aspect_min: float = 3.0,
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
    k = max(int(k_tophat_min), (min(h, w) // 60) * 2 + 1)
    k = _ensure_odd_positive(k, minimum=3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))

    tophat = cv2.morphologyEx(V, cv2.MORPH_TOPHAT, kernel)
    tophat_norm = cv2.normalize(tophat, None, 0, 255, cv2.NORM_MINMAX)
    debug["11_tophat_V_norm"] = tophat_norm

    # 4) Threshold tophat (Otsu) and combine with white mask
    _, th_otsu = cv2.threshold(tophat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    debug["12_tophat_otsu_mask"] = th_otsu

    combined = cv2.bitwise_and(th_otsu, white_hsv)
    debug["13_combined_mask_raw"] = combined

    # 5) Morphology cleanup
    # - OPEN은 얇은 라인을 침식 단계에서 날려버리기 쉬움 → 기본 False
    # - CLOSE는 작게 1회 권장
    k_close = _ensure_odd_positive(k_close, minimum=3)
    close_iter = max(int(close_iter), 1)

    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (k_close, k_close))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close, iterations=close_iter)
    debug["14a_mask_close_only"] = closed

    cleaned = closed

    if use_open:
        k_open = _ensure_odd_positive(k_open, minimum=3)
        open_iter = max(int(open_iter), 1)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (k_open, k_open))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel_open, iterations=open_iter)
        debug["14b_mask_open_applied"] = cleaned

    if use_median:
        median_ksize = _ensure_odd_positive(median_ksize, minimum=3)
        cleaned = cv2.medianBlur(cleaned, median_ksize)
        debug["14c_mask_median"] = cleaned

    debug["14_mask_morph_clean"] = cleaned

    # 6) Remove tiny connected components (area + elongation)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    filtered = np.zeros_like(cleaned)
    cc_area_min = max(int(cc_area_min), 1)
    cc_aspect_min = float(cc_aspect_min)

    for i in range(1, num):
        x, y, ww, hh, area = stats[i]
        if area < cc_area_min:
            continue

        # elongated bbox => line-like
        ar = max(ww, hh) / max(1, min(ww, hh))
        if ar >= cc_aspect_min:
            filtered[labels == i] = 255

    debug["15_mask_cc_filtered"] = filtered

    # 7) Overlay for quick inspection
    overlay = bgr.copy()
    overlay[filtered > 0] = (0, 0, 255)  # red in BGR
    alpha = 0.55
    blend = cv2.addWeighted(bgr, 1 - alpha, overlay, alpha, 0)
    debug["20_overlay_red_lines"] = blend

    return filtered, debug


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input image")
    parser.add_argument("--out_root", default="results", help="Output root folder name under CWD")
    parser.add_argument("--zip", action="store_true", help="Zip output images")

    # Thresholds
    parser.add_argument("--s_th", type=int, default=70, help="HSV saturation upper threshold for white-ish pixels")
    parser.add_argument("--v_th", type=int, default=160, help="HSV value lower threshold for white-ish pixels")

    # Top-hat
    parser.add_argument("--k_tophat_min", type=int, default=15, help="Minimum kernel size for top-hat")

    # Morphology
    parser.add_argument("--k_close", type=int, default=3)
    parser.add_argument("--close_iter", type=int, default=1)

    parser.add_argument("--use_open", action="store_true")
    parser.add_argument("--k_open", type=int, default=3)
    parser.add_argument("--open_iter", type=int, default=1)

    parser.add_argument("--no_median", action="store_true")
    parser.add_argument("--median_ksize", type=int, default=3)

    # CC filtering
    parser.add_argument("--cc_area_min", type=int, default=30)
    parser.add_argument("--cc_aspect_min", type=float, default=3.0)

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
        k_tophat_min=args.k_tophat_min,
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

    # Save all debug images
    for name, im in debug.items():
        save_png(out_dir, name, im)

    # Save final mask explicitly
    save_png(out_dir, "99_final_white_line_mask", final_mask)

    if args.zip:
        zip_path = out_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out_dir.glob("*.png")):
                z.write(p, arcname=p.name)
        print(f"[INFO] Zipped: {zip_path}")

    print("[DONE]")


if __name__ == "__main__":
    main()

# python get_linemask.py --input bmt_fullcourt_preload.png --out_root results