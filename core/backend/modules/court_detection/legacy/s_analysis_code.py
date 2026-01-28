#!/usr/bin/env python3
"""
S Channel Analysis Tool for White Region Detection

HSV 변환 후 S 채널의 다양한 임계값으로 흰색 영역을 추출하고 시각화합니다.
"""

import argparse
import datetime
import uuid
from pathlib import Path

import cv2
import numpy as np


def make_output_dir(root_dir: str) -> Path:
    """
    결과 저장 디렉토리 생성
    Format: {root_dir}/YYYYMMDD_HHMMSS_{uuid}
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    run_id = f"{timestamp}_{unique_id}"
    
    out_dir = Path(root_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    
    return out_dir


def save_image(out_dir: Path, name: str, img: np.ndarray):
    """이미지 저장"""
    path = out_dir / f"{name}.png"
    cv2.imwrite(str(path), img)
    print(f"[SAVED] {path}")


def analyze_s_channel(bgr_img: np.ndarray, out_dir: Path):
    """
    S 채널 분석 및 흰색 영역 추출
    
    Args:
        bgr_img: 입력 BGR 이미지
        out_dir: 결과 저장 디렉토리
    """
    h, w = bgr_img.shape[:2]
    
    # 1. HSV 변환
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = cv2.split(hsv)
    
    # 원본 이미지 저장
    save_image(out_dir, "00_original", bgr_img)
    
    # HSV 각 채널 저장
    save_image(out_dir, "01_h_channel", h_ch)
    save_image(out_dir, "01_s_channel", s_ch)
    save_image(out_dir, "01_v_channel", v_ch)
    
    # 2. S 채널 통계 정보 출력
    s_min, s_max = s_ch.min(), s_ch.max()
    s_mean, s_std = s_ch.mean(), s_ch.std()
    
    print(f"\n[S Channel Statistics]")
    print(f"  Min: {s_min}, Max: {s_max}")
    print(f"  Mean: {s_mean:.2f}, Std: {s_std:.2f}")
    
    # 통계 정보를 텍스트 파일로 저장
    stats_file = out_dir / "s_channel_stats.txt"
    with open(stats_file, "w") as f:
        f.write(f"S Channel Statistics\n")
        f.write(f"====================\n")
        f.write(f"Min: {s_min}\n")
        f.write(f"Max: {s_max}\n")
        f.write(f"Mean: {s_mean:.2f}\n")
        f.write(f"Std: {s_std:.2f}\n")
    print(f"[SAVED] {stats_file}")
    
    # 3. 다양한 S 임계값으로 흰색 영역 추출
    # 흰색은 채도(S)가 낮은 영역
    s_thresholds = [30, 50, 70, 90, 110, 130]
    
    results = []
    
    for s_th in s_thresholds:
        # S 채널이 임계값보다 작은 영역 = 흰색에 가까운 영역
        mask = (s_ch < s_th).astype(np.uint8) * 255
        
        # 흰색 배경 생성
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        
        # 검출된 영역을 검정색으로 표시
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]  # 검정색 (BGR)
        
        # 원본 이미지와 결과를 수평으로 연결
        h_concat = np.hstack([bgr_img, result])
        
        # 텍스트 추가
        text = f"S < {s_th}"
        cv2.putText(h_concat, text, (w + 20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3, cv2.LINE_AA)
        
        # 검출된 픽셀 비율 계산
        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
        
        # 저장
        save_image(out_dir, f"02_s_threshold_{s_th:03d}", h_concat)
        
        results.append({
            's_threshold': s_th,
            'detected_ratio': detected_ratio,
            'mask': mask
        })
        
        print(f"  S < {s_th}: {detected_ratio:.2f}% detected")
    
    # 4. V 채널도 함께 고려한 흰색 영역 추출
    print(f"\n[Combined S & V Channel Analysis]")
    
    # 흰색: S가 낮고 V가 높은 영역
    combined_configs = [
        {'s_max': 90, 'v_min': 150, 'name': 's90_v150'},
        {'s_max': 70, 'v_min': 170, 'name': 's70_v170'},
        {'s_max': 50, 'v_min': 180, 'name': 's50_v180'},
    ]
    
    for config in combined_configs:
        s_max = config['s_max']
        v_min = config['v_min']
        name = config['name']
        
        # 마스크 생성: S가 낮고 V가 높은 영역
        mask = ((s_ch < s_max) & (v_ch > v_min)).astype(np.uint8) * 255
        
        # 흰색 배경에 검정색으로 표시
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]  # 검정색 (BGR)
        
        # 원본과 연결
        h_concat = np.hstack([bgr_img, result])
        
        # 텍스트 추가
        text = f"S<{s_max} & V>{v_min}"
        cv2.putText(h_concat, text, (w + 20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3, cv2.LINE_AA)
        
        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
        
        save_image(out_dir, f"03_combined_{name}", h_concat)
        
        print(f"  S<{s_max} & V>{v_min}: {detected_ratio:.2f}% detected")
    
    # 5. S 채널 히스토그램 생성
    hist_img = create_histogram_image(s_ch, "S Channel Histogram", s_thresholds)
    save_image(out_dir, "04_s_histogram", hist_img)


def analyze_ycbcr_channel(bgr_img: np.ndarray, out_dir: Path):
    """
    YCbCr Y 채널 분석 및 흰색 영역 추출
    
    Args:
        bgr_img: 입력 BGR 이미지
        out_dir: 결과 저장 디렉토리
    """
    h, w = bgr_img.shape[:2]
    
    print(f"\n[YCbCr Y Channel Analysis]")
    
    # 1. YCbCr 변환
    ycbcr = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
    y_ch, cr_ch, cb_ch = cv2.split(ycbcr)
    
    # YCbCr 각 채널 저장
    save_image(out_dir, "05_y_channel", y_ch)
    save_image(out_dir, "05_cr_channel", cr_ch)
    save_image(out_dir, "05_cb_channel", cb_ch)
    
    # 2. Y 채널 통계 정보
    y_min, y_max = y_ch.min(), y_ch.max()
    y_mean, y_std = y_ch.mean(), y_ch.std()
    
    print(f"  Min: {y_min}, Max: {y_max}")
    print(f"  Mean: {y_mean:.2f}, Std: {y_std:.2f}")
    
    # 통계 정보 저장
    stats_file = out_dir / "y_channel_stats.txt"
    with open(stats_file, "w") as f:
        f.write(f"Y Channel Statistics\n")
        f.write(f"====================\n")
        f.write(f"Min: {y_min}\n")
        f.write(f"Max: {y_max}\n")
        f.write(f"Mean: {y_mean:.2f}\n")
        f.write(f"Std: {y_std:.2f}\n")
    print(f"[SAVED] {stats_file}")
    
    # 3. 다양한 Y 임계값으로 흰색 영역 추출
    # 흰색은 밝기(Y)가 높은 영역
    y_thresholds = [180, 190, 200, 210, 220, 230]
    
    for y_th in y_thresholds:
        # Y 채널이 임계값보다 큰 영역 = 밝은 영역 (흰색)
        mask = (y_ch > y_th).astype(np.uint8) * 255
        
        # 흰색 배경에 검정색으로 표시
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]  # 검정색 (BGR)
        
        # 원본과 연결
        h_concat = np.hstack([bgr_img, result])
        
        # 텍스트 추가
        text = f"Y > {y_th}"
        cv2.putText(h_concat, text, (w + 20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3, cv2.LINE_AA)
        
        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)
        
        save_image(out_dir, f"06_y_threshold_{y_th:03d}", h_concat)
        
        print(f"  Y > {y_th}: {detected_ratio:.2f}% detected")
    
    # 4. Y 채널 히스토그램
    hist_img = create_histogram_image(y_ch, "Y Channel Histogram", y_thresholds)
    save_image(out_dir, "07_y_histogram", hist_img)


def analyze_lab_channel(bgr_img: np.ndarray, out_dir: Path):
    """
    LAB L 채널 분석 및 흰색 영역 추출
    
    Args:
        bgr_img: 입력 BGR 이미지
        out_dir: 결과 저장 디렉토리
    """
    h, w = bgr_img.shape[:2]
    
    print(f"\n[LAB L Channel Analysis]")
    
    # 1. LAB 변환
    lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    
    # LAB 각 채널 저장
    save_image(out_dir, "08_l_channel", l_ch)
    save_image(out_dir, "08_a_channel", a_ch)
    save_image(out_dir, "08_b_channel", b_ch)
    
    # 2. L 채널 통계 정보
    l_min, l_max = l_ch.min(), l_ch.max()
    l_mean, l_std = l_ch.mean(), l_ch.std()
    
    print(f"  Min: {l_min}, Max: {l_max}")
    print(f"  Mean: {l_mean:.2f}, Std: {l_std:.2f}")
    
    # 통계 정보 저장
    stats_file = out_dir / "l_channel_stats.txt"
    with open(stats_file, "w") as f:
        f.write(f"L Channel Statistics\n")
        f.write(f"====================\n")
        f.write(f"Min: {l_min}\n")
        f.write(f"Max: {l_max}\n")
        f.write(f"Mean: {l_mean:.2f}\n")
        f.write(f"Std: {l_std:.2f}\n")
    print(f"[SAVED] {stats_file}")
    
    # 3. 다양한 L 임계값으로 흰색 영역 추출
    # 흰색은 명도(L)가 높은 영역
    l_thresholds = [180, 190, 200, 210, 220, 230]
    
    for l_th in l_thresholds:
        # L 채널이 임계값보다 큰 영역 = 밝은 영역 (흰색)
        mask = (l_ch > l_th).astype(np.uint8) * 255
        
        # 흰색 배경에 검정색으로 표시
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask > 0] = [0, 0, 0]  # 검정색 (BGR)
        
        # 원본과 연결
        h_concat = np.hstack([bgr_img, result])
        
        # 텍스트 추가
        text = f"L > {l_th}"
        cv2.putText(h_concat, text, (w + 20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (180, 105, 255), 3, cv2.LINE_AA)
        
        detected_ratio = (mask > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 105, 255), 2, cv2.LINE_AA)
        
        save_image(out_dir, f"09_l_threshold_{l_th:03d}", h_concat)
        
        print(f"  L > {l_th}: {detected_ratio:.2f}% detected")
    
    # 4. L 채널 히스토그램
    hist_img = create_histogram_image(l_ch, "L Channel Histogram", l_thresholds)
    save_image(out_dir, "10_l_histogram", hist_img)


def analyze_ensemble(bgr_img: np.ndarray, out_dir: Path):
    """
    HSV, YCbCr, LAB 앙상블 분석
    
    Args:
        bgr_img: 입력 BGR 이미지
        out_dir: 결과 저장 디렉토리
    """
    h, w = bgr_img.shape[:2]
    
    print(f"\n[Ensemble Analysis - Multi Color Space]")
    
    # 각 컬러스페이스 변환
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    ycbcr = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
    lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)
    
    h_ch, s_ch, v_ch = cv2.split(hsv)
    y_ch, cr_ch, cb_ch = cv2.split(ycbcr)
    l_ch, a_ch, b_ch = cv2.split(lab)
    
    # 앙상블 설정
    ensemble_configs = [
        {
            'name': 'conservative',
            'desc': 'HSV AND YCbCr AND LAB',
            's_max': 90, 'v_min': 150,
            'y_min': 200,
            'l_min': 200,
            'operation': 'and'
        },
        {
            'name': 'moderate',
            'desc': 'At least 2 of 3',
            's_max': 90, 'v_min': 150,
            'y_min': 200,
            'l_min': 200,
            'operation': 'voting'
        },
        {
            'name': 'aggressive',
            'desc': 'HSV OR YCbCr OR LAB',
            's_max': 90, 'v_min': 150,
            'y_min': 200,
            'l_min': 200,
            'operation': 'or'
        },
    ]
    
    for config in ensemble_configs:
        # 각 컬러스페이스별 마스크
        mask_hsv = ((s_ch < config['s_max']) & (v_ch > config['v_min'])).astype(np.uint8)
        mask_ycbcr = (y_ch > config['y_min']).astype(np.uint8)
        mask_lab = (l_ch > config['l_min']).astype(np.uint8)
        
        # 앙상블 연산
        if config['operation'] == 'and':
            mask_final = (mask_hsv & mask_ycbcr & mask_lab) * 255
        elif config['operation'] == 'voting':
            mask_final = ((mask_hsv.astype(int) + mask_ycbcr.astype(int) + mask_lab.astype(int)) >= 2).astype(np.uint8) * 255
        else:  # or
            mask_final = (mask_hsv | mask_ycbcr | mask_lab) * 255
        
        # 시각화
        white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
        result = white_bg.copy()
        result[mask_final > 0] = [0, 0, 0]
        
        h_concat = np.hstack([bgr_img, result])
        
        # 텍스트
        text = f"Ensemble: {config['name']}"
        cv2.putText(h_concat, text, (w + 20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 128, 0), 3, cv2.LINE_AA)
        
        detected_ratio = (mask_final > 0).sum() / (h * w) * 100
        ratio_text = f"Detected: {detected_ratio:.2f}%"
        cv2.putText(h_concat, ratio_text, (w + 20, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 128, 0), 2, cv2.LINE_AA)
        
        desc_text = config['desc']
        cv2.putText(h_concat, desc_text, (w + 20, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 2, cv2.LINE_AA)
        
        save_image(out_dir, f"11_ensemble_{config['name']}", h_concat)
        
        print(f"  {config['name']}: {detected_ratio:.2f}% detected")
    
    print(f"\n[DONE] All results saved to: {out_dir}")


def create_histogram_image(channel: np.ndarray, title: str, thresholds: list) -> np.ndarray:
    """
    채널 히스토그램 이미지 생성
    """
    hist_height = 400
    hist_width = 512
    
    # 히스토그램 계산
    hist = cv2.calcHist([channel], [0], None, [256], [0, 256])
    
    # 정규화
    hist_norm = hist / hist.max() * (hist_height - 50)
    
    # 이미지 생성
    hist_img = np.ones((hist_height, hist_width, 3), dtype=np.uint8) * 255
    
    # 히스토그램 그리기
    bin_width = hist_width / 256
    for i in range(256):
        x = int(i * bin_width)
        y = int(hist_norm[i])
        cv2.line(hist_img, (x, hist_height - 30), (x, hist_height - 30 - y), 
                (100, 100, 100), 1)
    
    # 임계값 선 그리기
    for th in thresholds:
        x = int(th * bin_width)
        cv2.line(hist_img, (x, 0), (x, hist_height - 30), (0, 0, 255), 2)
        cv2.putText(hist_img, str(th), (x - 10, 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    
    # 제목 추가
    cv2.putText(hist_img, title, (10, hist_height - 10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
    # 축 레이블
    cv2.putText(hist_img, "0", (5, hist_height - 35), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.putText(hist_img, "255", (hist_width - 30, hist_height - 35), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    
    return hist_img


def main():
    parser = argparse.ArgumentParser(
        description="S Channel Analysis Tool for White Region Detection"
    )
    parser.add_argument(
        "--input", 
        required=True, 
        help="Path to input image file"
    )
    parser.add_argument(
        "--out_root", 
        required=True, 
        help="Root directory for output results"
    )
    
    args = parser.parse_args()
    
    # 입력 이미지 읽기
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {args.input}")
    
    bgr_img = cv2.imread(str(input_path))
    if bgr_img is None:
        raise ValueError(f"Failed to read image: {args.input}")
    
    print(f"[INFO] Input image: {input_path}")
    print(f"[INFO] Image size: {bgr_img.shape[1]}x{bgr_img.shape[0]}")
    
    # 출력 디렉토리 생성
    out_dir = make_output_dir(args.out_root)
    print(f"[INFO] Output directory: {out_dir}")
    
    # 1. HSV S 채널 분석 수행
    analyze_s_channel(bgr_img, out_dir)
    
    # 2. YCbCr Y 채널 분석 수행
    analyze_ycbcr_channel(bgr_img, out_dir)
    
    # 3. LAB L 채널 분석 수행
    analyze_lab_channel(bgr_img, out_dir)
    
    # 4. 앙상블 분석 수행
    analyze_ensemble(bgr_img, out_dir)


if __name__ == "__main__":
    main()


"""
python s_analysis_code.py --input source_image/pro_court.png --out_root s_analysis_results
python s_analysis_code.py --input source_image/amatuer_court.jpg --out_root s_analysis_results

# 2
python s_analysis_code.py --input source_image/pro_court_highangle.png --out_root s_analysis_results

# 3
python s_analysis_code.py --input source_image/pro_court_topview.png --out_root s_analysis_results

# 4
python s_analysis_code.py --input source_image/amatuer_court.jpg --out_root s_analysis_results

## s_analysis_code.py
 - 원본 png 이미지에서, 멀티 컬러스페이스 채널 정보 기반 혼합마스크 생성
 - 3개의 컬러스페이스 추출 결과를 종합하여 최종 마스크 생성

# todo
 1. pro_court 기반 검출 수행 (완료)
 2. pro_court_highangle 기반 검출 수행
 3. pro_court_topview 기반 검출 수행
 4. amatuar_court 기반 검출 수행

"""