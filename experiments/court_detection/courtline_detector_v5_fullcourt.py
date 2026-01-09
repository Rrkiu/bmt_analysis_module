"""
배드민턴 코트 라인 검출 v6 - Full Court Support
================================================
- 풀코트/반코트 모두 지원
- 풀코트 레퍼런스 라인 생성 및 원본 이미지 오버레이
- Edge First 방식
- 코트 규격 기반 동적 분류
"""

import cv2
import numpy as np
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import math


# ============================================================
# 배드민턴 코트 규격 (BWF 공식 규격, 단위: 미터)
# ============================================================
COURT_SPEC = {
    # 가로 (X 방향)
    'width_doubles': 5.18,       # 복식 전체 폭
    'width_singles': 4.26,       # 단식 폭 (5.18 - 0.46*2)
    'singles_offset': 0.46,      # 단식 라인 오프셋 (복식 외곽에서 안쪽)
    'center_x': 2.59,            # 센터라인 X 위치 (5.18 / 2)
    
    # 세로 (Y 방향) - 반코트
    'half_length': 6.70,         # 반코트 길이
    'short_service': 1.98,       # 숏서비스 라인 (네트에서)
    'long_service': 5.94,        # 복식 롱서비스 라인 (네트에서)
    
    # 세로 (Y 방향) - 풀코트
    'full_length': 13.40,        # 풀코트 길이 (6.70 * 2)
    'net_position': 6.70,        # 네트 위치 (풀코트 중앙)
}

# 풀코트 라인 위치 (미터) - Y=0이 한쪽 베이스라인
FULLCOURT_LINE_POSITIONS = {
    # X 좌표 (가로)
    'sideline_left_doubles': 0.0,
    'sideline_left_singles': 0.46,
    'center': 2.59,
    'sideline_right_singles': 4.72,  # 5.18 - 0.46
    'sideline_right_doubles': 5.18,
    
    # Y 좌표 (세로) - 풀코트 기준
    'baseline_near': 0.0,             # 가까운 쪽 베이스라인
    'long_service_near': 0.76,        # 가까운 쪽 롱서비스 (6.70 - 5.94)
    'short_service_near': 4.72,       # 가까운 쪽 숏서비스 (6.70 - 1.98)
    'net': 6.70,                      # 네트
    'short_service_far': 8.68,        # 먼 쪽 숏서비스 (6.70 + 1.98)
    'long_service_far': 12.64,        # 먼 쪽 롱서비스 (6.70 + 5.94)
    'baseline_far': 13.40,            # 먼 쪽 베이스라인
}

# 반코트 라인 위치 (기존 호환)
HALFCOURT_LINE_POSITIONS = {
    # X 좌표
    'sideline_left_doubles': 0.0,
    'sideline_left_singles': 0.46,
    'center': 2.59,
    'sideline_right_singles': 4.72,
    'sideline_right_doubles': 5.18,
    # Y 좌표
    'net': 0.0,
    'short_service': 1.98,
    'long_service': 5.94,
    'baseline': 6.70,
}


@dataclass
class DetectedLine:
    p1: Tuple[int, int]
    p2: Tuple[int, int]
    angle: float
    length: float
    line_type: Optional[str] = None
    category: Optional[str] = None
    distance_to_ref: Optional[float] = None
    
    @property
    def midpoint(self) -> Tuple[float, float]:
        return ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)
    
    @property
    def y_center(self) -> float:
        return (self.p1[1] + self.p2[1]) / 2
    
    @property
    def x_center(self) -> float:
        return (self.p1[0] + self.p2[0]) / 2


@dataclass
class CourtCalibration:
    """코트 캘리브레이션 정보"""
    warped_width: int
    warped_height: int
    pixels_per_meter_x: float
    pixels_per_meter_y: float
    is_full_court: bool = False
    tolerance_meters: float = 0.20
    
    @classmethod
    def from_warped_size(cls, warped_width: int, warped_height: int, 
                         is_full_court: bool = False, tolerance: float = 0.20):
        """Bird's Eye View 크기에서 캘리브레이션 생성"""
        court_length = COURT_SPEC['full_length'] if is_full_court else COURT_SPEC['half_length']
        ppm_x = warped_width / COURT_SPEC['width_doubles']
        ppm_y = warped_height / court_length
        return cls(warped_width, warped_height, ppm_x, ppm_y, is_full_court, tolerance)
    
    def pixels_to_meters(self, x_pixels: float, y_pixels: float) -> Tuple[float, float]:
        x_meters = x_pixels / self.pixels_per_meter_x
        y_meters = y_pixels / self.pixels_per_meter_y
        return x_meters, y_meters
    
    def meters_to_pixels(self, x_meters: float, y_meters: float) -> Tuple[int, int]:
        x_pixels = int(x_meters * self.pixels_per_meter_x)
        y_pixels = int(y_meters * self.pixels_per_meter_y)
        return x_pixels, y_pixels
    
    @property
    def tolerance_pixels_x(self) -> float:
        return self.tolerance_meters * self.pixels_per_meter_x
    
    @property
    def tolerance_pixels_y(self) -> float:
        return self.tolerance_meters * self.pixels_per_meter_y
    
    @property
    def line_positions(self) -> Dict:
        return FULLCOURT_LINE_POSITIONS if self.is_full_court else HALFCOURT_LINE_POSITIONS


def perspective_transform(image, corners, output_size=None, is_full_court=False):
    """원근 변환"""
    tl, tr, br, bl = [np.array(c, dtype=np.float32) for c in corners]
    
    if output_size is None:
        width_top = np.linalg.norm(tr - tl)
        width_bottom = np.linalg.norm(br - bl)
        width = int(max(width_top, width_bottom))
        
        court_length = COURT_SPEC['full_length'] if is_full_court else COURT_SPEC['half_length']
        court_ratio = court_length / COURT_SPEC['width_doubles']
        height = int(width * court_ratio)
    else:
        width, height = output_size
    
    src_pts = np.array([tl, tr, br, bl], dtype=np.float32)
    dst_pts = np.array([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype=np.float32)
    
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    M_inv = cv2.getPerspectiveTransform(dst_pts, src_pts)
    warped = cv2.warpPerspective(image, M, (width, height))
    
    return warped, M, M_inv


# ============================================================
# 풀코트 레퍼런스 라인 생성
# ============================================================

def generate_fullcourt_reference_lines(calibration: CourtCalibration) -> List[DetectedLine]:
    """
    풀코트 기준 레퍼런스 라인 생성
    - 실제 코트 규격에 맞는 모든 라인을 픽셀 좌표로 생성
    """
    lines = []
    pos = FULLCOURT_LINE_POSITIONS
    w, h = calibration.warped_width, calibration.warped_height
    
    # 수평선 (가로로 가는 라인들)
    horizontal_lines = [
        ('baseline_near', pos['baseline_near']),
        ('long_service_near', pos['long_service_near']),
        ('short_service_near', pos['short_service_near']),
        ('net', pos['net']),
        ('short_service_far', pos['short_service_far']),
        ('long_service_far', pos['long_service_far']),
        ('baseline_far', pos['baseline_far']),
    ]
    
    for name, y_meters in horizontal_lines:
        y_px = calibration.meters_to_pixels(0, y_meters)[1]
        lines.append(DetectedLine(
            p1=(0, y_px), p2=(w, y_px),
            angle=0.0, length=w,
            line_type='horizontal', category=name
        ))
    
    # 수직선 (세로로 가는 라인들)
    vertical_lines = [
        ('sideline_left_doubles', pos['sideline_left_doubles']),
        ('sideline_left_singles', pos['sideline_left_singles']),
        ('sideline_right_singles', pos['sideline_right_singles']),
        ('sideline_right_doubles', pos['sideline_right_doubles']),
    ]
    
    for name, x_meters in vertical_lines:
        x_px = calibration.meters_to_pixels(x_meters, 0)[0]
        lines.append(DetectedLine(
            p1=(x_px, 0), p2=(x_px, h),
            angle=90.0, length=h,
            line_type='vertical', category=name
        ))
    
    # 센터라인 (숏서비스 ~ 숏서비스 구간만)
    center_x = calibration.meters_to_pixels(pos['center'], 0)[0]
    short_near_y = calibration.meters_to_pixels(0, pos['short_service_near'])[1]
    short_far_y = calibration.meters_to_pixels(0, pos['short_service_far'])[1]
    
    # Near 쪽 센터라인 (baseline_near ~ short_service_near)
    baseline_near_y = calibration.meters_to_pixels(0, pos['baseline_near'])[1]
    lines.append(DetectedLine(
        p1=(center_x, baseline_near_y), p2=(center_x, short_near_y),
        angle=90.0, length=abs(short_near_y - baseline_near_y),
        line_type='vertical', category='center_near'
    ))
    
    # Far 쪽 센터라인 (short_service_far ~ baseline_far)
    baseline_far_y = calibration.meters_to_pixels(0, pos['baseline_far'])[1]
    lines.append(DetectedLine(
        p1=(center_x, short_far_y), p2=(center_x, baseline_far_y),
        angle=90.0, length=abs(baseline_far_y - short_far_y),
        line_type='vertical', category='center_far'
    ))
    
    return lines


def generate_halfcourt_reference_lines(calibration: CourtCalibration) -> List[DetectedLine]:
    """반코트 기준 레퍼런스 라인 생성"""
    lines = []
    pos = HALFCOURT_LINE_POSITIONS
    w, h = calibration.warped_width, calibration.warped_height
    
    # 수평선
    for name in ['net', 'short_service', 'long_service', 'baseline']:
        y_px = calibration.meters_to_pixels(0, pos[name])[1]
        lines.append(DetectedLine(
            p1=(0, y_px), p2=(w, y_px),
            angle=0.0, length=w,
            line_type='horizontal', category=name
        ))
    
    # 수직선
    for name in ['sideline_left_doubles', 'sideline_left_singles', 
                 'sideline_right_singles', 'sideline_right_doubles']:
        x_px = calibration.meters_to_pixels(pos[name], 0)[0]
        lines.append(DetectedLine(
            p1=(x_px, 0), p2=(x_px, h),
            angle=90.0, length=h,
            line_type='vertical', category=name
        ))
    
    # 센터라인
    center_x = calibration.meters_to_pixels(pos['center'], 0)[0]
    short_y = calibration.meters_to_pixels(0, pos['short_service'])[1]
    baseline_y = calibration.meters_to_pixels(0, pos['baseline'])[1]
    lines.append(DetectedLine(
        p1=(center_x, short_y), p2=(center_x, baseline_y),
        angle=90.0, length=abs(baseline_y - short_y),
        line_type='vertical', category='center'
    ))
    
    return lines


def transform_lines_to_original(lines: List[DetectedLine], M_inv: np.ndarray) -> List[DetectedLine]:
    """변환된 라인을 원본 좌표로 역변환"""
    transformed = []
    for line in lines:
        p1 = np.array([line.p1[0], line.p1[1], 1], dtype=np.float32)
        p2 = np.array([line.p2[0], line.p2[1], 1], dtype=np.float32)
        
        p1_orig = M_inv @ p1
        p2_orig = M_inv @ p2
        p1_orig = p1_orig[:2] / p1_orig[2]
        p2_orig = p2_orig[:2] / p2_orig[2]
        
        new_line = DetectedLine(
            p1=(int(p1_orig[0]), int(p1_orig[1])),
            p2=(int(p2_orig[0]), int(p2_orig[1])),
            angle=line.angle, length=line.length,
            line_type=line.line_type, category=line.category
        )
        transformed.append(new_line)
    
    return transformed


# ============================================================
# 시각화 함수
# ============================================================

COLORS = {
    # 수평선
    'net': (0, 165, 255),              # Orange
    'baseline': (0, 255, 0),            # Green
    'baseline_near': (0, 255, 0),       # Green
    'baseline_far': (0, 255, 0),        # Green
    'short_service': (0, 255, 255),     # Yellow
    'short_service_near': (0, 255, 255),
    'short_service_far': (0, 255, 255),
    'long_service': (255, 255, 0),      # Cyan
    'long_service_near': (255, 255, 0),
    'long_service_far': (255, 255, 0),
    # 수직선
    'center': (255, 0, 0),              # Blue
    'center_near': (255, 0, 0),
    'center_far': (255, 0, 0),
    'sideline_left_doubles': (255, 0, 255),    # Magenta
    'sideline_right_doubles': (255, 0, 255),
    'sideline_left_singles': (255, 150, 255),  # Light Pink
    'sideline_right_singles': (255, 150, 255),
}


def draw_reference_lines(image: np.ndarray, lines: List[DetectedLine], 
                         thickness: int = 2, alpha: float = 0.7) -> np.ndarray:
    """레퍼런스 라인을 이미지에 오버레이"""
    overlay = image.copy()
    
    for line in lines:
        color = COLORS.get(line.category, (128, 128, 128))
        cv2.line(overlay, line.p1, line.p2, color, thickness)
    
    # 알파 블렌딩
    result = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)
    return result


def draw_reference_lines_with_labels(image: np.ndarray, lines: List[DetectedLine], 
                                     thickness: int = 2) -> np.ndarray:
    """레퍼런스 라인 + 라벨 표시"""
    result = image.copy()
    
    for line in lines:
        color = COLORS.get(line.category, (128, 128, 128))
        cv2.line(result, line.p1, line.p2, color, thickness)
        
        # 라벨
        mid = line.midpoint
        label = line.category.replace('sideline_', 'SL_').replace('_', ' ')
        
        # 배경 박스
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
        cv2.rectangle(result, 
                     (int(mid[0]) - 2, int(mid[1]) - text_h - 4),
                     (int(mid[0]) + text_w + 2, int(mid[1]) + 2),
                     (0, 0, 0), -1)
        cv2.putText(result, label, (int(mid[0]), int(mid[1]) - 2),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
    
    return result


def draw_legend(image: np.ndarray, is_full_court: bool = False) -> np.ndarray:
    """레전드"""
    result = image.copy()
    
    if is_full_court:
        items = [
            ('Net Line', (0, 165, 255)),
            ('Short Service', (0, 255, 255)),
            ('Long Service', (255, 255, 0)),
            ('Baseline', (0, 255, 0)),
            ('Center Line', (255, 0, 0)),
            ('Sideline (Doubles)', (255, 0, 255)),
            ('Sideline (Singles)', (255, 150, 255)),
        ]
    else:
        items = [
            ('Net Line', (0, 165, 255)),
            ('Short Service', (0, 255, 255)),
            ('Long Service (Doubles)', (255, 255, 0)),
            ('Baseline', (0, 255, 0)),
            ('Center Line', (255, 0, 0)),
            ('Sideline (Doubles)', (255, 0, 255)),
            ('Sideline (Singles)', (255, 150, 255)),
        ]
    
    overlay = result.copy()
    cv2.rectangle(overlay, (5, 5), (230, 30 + 25 * len(items)), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, result, 0.3, 0, result)
    
    y = 30
    for label, color in items:
        cv2.rectangle(result, (10, y - 12), (25, y + 3), color, -1)
        cv2.putText(result, label, (30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        y += 25
    
    return result


def draw_calibration_info(image: np.ndarray, calibration: CourtCalibration) -> np.ndarray:
    """캘리브레이션 정보 표시"""
    result = image.copy()
    
    court_type = "Full Court" if calibration.is_full_court else "Half Court"
    court_length = COURT_SPEC['full_length'] if calibration.is_full_court else COURT_SPEC['half_length']
    
    info_lines = [
        f"Type: {court_type}",
        f"Court: {COURT_SPEC['width_doubles']}m x {court_length}m",
        f"PPM X: {calibration.pixels_per_meter_x:.1f}",
        f"PPM Y: {calibration.pixels_per_meter_y:.1f}",
    ]
    
    y = image.shape[0] - 20 - 20 * len(info_lines)
    for text in info_lines:
        cv2.putText(result, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        y += 20
    
    return result


# ============================================================
# 메인 처리 함수
# ============================================================

def process_fullcourt_reference(image_path: str, corners: List[List[int]], 
                                output_dir: str, name: str = "fullcourt") -> dict:
    """
    풀코트 레퍼런스 오버레이 처리
    
    Args:
        image_path: 원본 이미지 경로
        corners: 풀코트 4점 좌표 [TL, TR, BR, BL]
        output_dir: 출력 디렉토리
        name: 출력 파일 prefix
    
    Returns:
        결과 정보 딕셔너리
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    print(f"[INFO] Image: {image.shape}")
    print(f"[INFO] Corners (Full Court): {corners}")
    
    # Step 1: 원본 이미지 저장
    cv2.imwrite(os.path.join(output_dir, f"{name}_00_original.jpg"), image)
    
    # Step 2: Bird's Eye View 변환 (풀코트)
    print("\n[Step 2] Perspective Transform (Full Court)")
    warped, M, M_inv = perspective_transform(image, corners, is_full_court=True)
    warped_h, warped_w = warped.shape[:2]
    print(f"  Warped size: {warped_w} x {warped_h}")
    cv2.imwrite(os.path.join(output_dir, f"{name}_01_warped.jpg"), warped)
    
    # Step 3: 캘리브레이션 생성
    print("\n[Step 3] Create Calibration")
    calibration = CourtCalibration.from_warped_size(warped_w, warped_h, is_full_court=True)
    print(f"  Pixels per meter X: {calibration.pixels_per_meter_x:.2f}")
    print(f"  Pixels per meter Y: {calibration.pixels_per_meter_y:.2f}")
    
    # Step 4: 풀코트 레퍼런스 라인 생성 (Bird's Eye View 좌표)
    print("\n[Step 4] Generate Reference Lines")
    ref_lines = generate_fullcourt_reference_lines(calibration)
    print(f"  Generated {len(ref_lines)} reference lines")
    
    # Step 5: Bird's Eye View에 레퍼런스 라인 시각화
    print("\n[Step 5] Visualize on Bird's Eye View")
    warped_with_ref = draw_reference_lines_with_labels(warped, ref_lines, thickness=2)
    warped_with_ref = draw_legend(warped_with_ref, is_full_court=True)
    warped_with_ref = draw_calibration_info(warped_with_ref, calibration)
    cv2.imwrite(os.path.join(output_dir, f"{name}_02c_reference_bev.jpg"), warped_with_ref)
    
    # Step 6: 레퍼런스 라인을 원본 좌표로 역변환
    print("\n[Step 6] Transform Reference to Original")
    original_ref_lines = transform_lines_to_original(ref_lines, M_inv)
    
    # Step 7: 원본 이미지에 오버레이
    print("\n[Step 7] Overlay on Original Image")
    
    # 7a: 라인만 오버레이
    result_lines_only = draw_reference_lines(image, original_ref_lines, thickness=2, alpha=0.8)
    cv2.imwrite(os.path.join(output_dir, f"{name}_03_overlay_lines.jpg"), result_lines_only)
    
    # 7b: 라인 + 라벨 오버레이
    result_with_labels = draw_reference_lines_with_labels(image, original_ref_lines, thickness=2)
    result_with_labels = draw_legend(result_with_labels, is_full_court=True)
    cv2.imwrite(os.path.join(output_dir, f"{name}_04_overlay_labeled.jpg"), result_with_labels)
    
    # 결과 JSON
    results = {
        'image_path': image_path,
        'court_type': 'full_court',
        'corners': corners,
        'calibration': {
            'warped_size': [warped_w, warped_h],
            'pixels_per_meter_x': float(calibration.pixels_per_meter_x),
            'pixels_per_meter_y': float(calibration.pixels_per_meter_y),
        },
        'reference_lines': [
            {
                'category': l.category,
                'original_coords': {'p1': list(l.p1), 'p2': list(l.p2)},
            }
            for l in original_ref_lines
        ]
    }
    
    with open(os.path.join(output_dir, f"{name}_results.json"), 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[INFO] Results saved to {output_dir}")
    return results


def load_json_config(json_path):
    """JSON 설정 파일 로드"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='배드민턴 코트 라인 검출 v6 - Full Court Reference Overlay'
    )
    parser.add_argument('json_path', type=str, help='JSON 설정 파일 경로')
    parser.add_argument('-o', '--output', type=str, default='.', help='출력 디렉토리')
    parser.add_argument('--full-court', action='store_true', help='풀코트 모드 (기본: 반코트)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.json_path):
        print(f"[ERROR] JSON file not found: {args.json_path}")
        return
    
    config = load_json_config(args.json_path)
    test_cases = config.get('test_cases', [])
    
    if not test_cases:
        print("[ERROR] No test_cases found")
        return
    
    for idx, tc in enumerate(test_cases, 1):
        name = tc.get('name', f'test_{idx}')
        image_path = tc.get('image_path')
        area = tc.get('area')
        is_full = tc.get('is_full_court', args.full_court)
        
        if not os.path.exists(image_path):
            print(f"[ERROR] Image not found: {image_path}")
            continue
        
        corners = [[int(p[0]), int(p[1])] for p in area]
        
        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        output_dir = os.path.join(args.output, f"court_ref_{name}_{timestamp}")
        
        print(f"\n{'='*60}")
        print(f"Processing: {name} ({'Full Court' if is_full else 'Half Court'})")
        print(f"{'='*60}")
        
        if is_full:
            process_fullcourt_reference(image_path, corners, output_dir, name)
        else:
            # 반코트는 기존 로직 사용 가능 (여기서는 레퍼런스 오버레이만)
            process_halfcourt_reference(image_path, corners, output_dir, name)


def process_halfcourt_reference(image_path: str, corners: List[List[int]], 
                                output_dir: str, name: str = "halfcourt") -> dict:
    """반코트 레퍼런스 오버레이 처리"""
    os.makedirs(output_dir, exist_ok=True)
    
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")
    
    cv2.imwrite(os.path.join(output_dir, f"{name}_00_original.jpg"), image)
    
    warped, M, M_inv = perspective_transform(image, corners, is_full_court=False)
    warped_h, warped_w = warped.shape[:2]
    cv2.imwrite(os.path.join(output_dir, f"{name}_01_warped.jpg"), warped)
    
    calibration = CourtCalibration.from_warped_size(warped_w, warped_h, is_full_court=False)
    
    ref_lines = generate_halfcourt_reference_lines(calibration)
    
    warped_with_ref = draw_reference_lines_with_labels(warped, ref_lines, thickness=2)
    warped_with_ref = draw_legend(warped_with_ref, is_full_court=False)
    warped_with_ref = draw_calibration_info(warped_with_ref, calibration)
    cv2.imwrite(os.path.join(output_dir, f"{name}_02c_reference_bev.jpg"), warped_with_ref)
    
    original_ref_lines = transform_lines_to_original(ref_lines, M_inv)
    
    result_lines_only = draw_reference_lines(image, original_ref_lines, thickness=2, alpha=0.8)
    cv2.imwrite(os.path.join(output_dir, f"{name}_03_overlay_lines.jpg"), result_lines_only)
    
    result_with_labels = draw_reference_lines_with_labels(image, original_ref_lines, thickness=2)
    result_with_labels = draw_legend(result_with_labels, is_full_court=False)
    cv2.imwrite(os.path.join(output_dir, f"{name}_04_overlay_labeled.jpg"), result_with_labels)
    
    results = {
        'image_path': image_path,
        'court_type': 'half_court',
        'corners': corners,
        'calibration': {
            'warped_size': [warped_w, warped_h],
            'pixels_per_meter_x': float(calibration.pixels_per_meter_x),
            'pixels_per_meter_y': float(calibration.pixels_per_meter_y),
        },
        'reference_lines': [
            {
                'category': l.category,
                'original_coords': {'p1': list(l.p1), 'p2': list(l.p2)},
            }
            for l in original_ref_lines
        ]
    }
    
    with open(os.path.join(output_dir, f"{name}_results.json"), 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"[INFO] Results saved to {output_dir}")
    return results


if __name__ == "__main__":
    main()