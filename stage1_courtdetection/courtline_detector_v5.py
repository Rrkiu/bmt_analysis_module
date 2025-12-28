"""
배드민턴 코트 라인 검출 v4
========================
- Edge First 방식
- 코트 규격 기반 동적 분류 (하드코딩 제거)
- 단식/복식 사이드라인 구분
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
    
    # 세로 (Y 방향) - 네트 기준
    'half_length': 6.70,         # 반코트 길이
    'short_service': 1.98,       # 숏서비스 라인 (네트에서)
    'long_service': 5.94,        # 복식 롱서비스 라인 (네트에서)
    
    # 라인 분류용 기준점 (미터)
    'line_positions': {
        # X 좌표 기준점
        'sideline_left_doubles': 0.0,
        'sideline_left_singles': 0.46,
        'center': 2.59,
        'sideline_right_singles': 4.72,  # 5.18 - 0.46
        'sideline_right_doubles': 5.18,
        # Y 좌표 기준점
        'net': 0.0,
        'short_service': 1.98,
        'long_service': 5.94,
        'baseline': 6.70,
    }
}


@dataclass
class DetectedLine:
    p1: Tuple[int, int]
    p2: Tuple[int, int]
    angle: float
    length: float
    line_type: Optional[str] = None
    category: Optional[str] = None
    distance_to_ref: Optional[float] = None  # 기준점과의 거리 (미터)
    
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
    tolerance_meters: float = 0.20  # 허용 오차 (20cm)
    
    @classmethod
    def from_warped_size(cls, warped_width: int, warped_height: int, tolerance: float = 0.20):
        """Bird's Eye View 크기에서 캘리브레이션 생성"""
        ppm_x = warped_width / COURT_SPEC['width_doubles']
        ppm_y = warped_height / COURT_SPEC['half_length']
        return cls(warped_width, warped_height, ppm_x, ppm_y, tolerance)
    
    def pixels_to_meters(self, x_pixels: float, y_pixels: float) -> Tuple[float, float]:
        """픽셀 좌표를 미터로 변환"""
        x_meters = x_pixels / self.pixels_per_meter_x
        y_meters = y_pixels / self.pixels_per_meter_y
        return x_meters, y_meters
    
    def meters_to_pixels(self, x_meters: float, y_meters: float) -> Tuple[int, int]:
        """미터를 픽셀 좌표로 변환"""
        x_pixels = int(x_meters * self.pixels_per_meter_x)
        y_pixels = int(y_meters * self.pixels_per_meter_y)
        return x_pixels, y_pixels
    
    @property
    def tolerance_pixels_x(self) -> float:
        return self.tolerance_meters * self.pixels_per_meter_x
    
    @property
    def tolerance_pixels_y(self) -> float:
        return self.tolerance_meters * self.pixels_per_meter_y


def create_output_dir(base_path="."):
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    output_dir = os.path.join(base_path, f"court_lines_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def perspective_transform(image, corners, output_size=None):
    """원근 변환"""
    tl, tr, br, bl = [np.array(c, dtype=np.float32) for c in corners]
    
    if output_size is None:
        width_top = np.linalg.norm(tr - tl)
        width_bottom = np.linalg.norm(br - bl)
        width = int(max(width_top, width_bottom))
        court_ratio = COURT_SPEC['half_length'] / COURT_SPEC['width_doubles']
        height = int(width * court_ratio)
    else:
        width, height = output_size
    
    src_pts = np.array([tl, tr, br, bl], dtype=np.float32)
    dst_pts = np.array([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype=np.float32)
    
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    M_inv = cv2.getPerspectiveTransform(dst_pts, src_pts)
    warped = cv2.warpPerspective(image, M, (width, height))
    
    return warped, M, M_inv


def detect_edges_in_roi(image, corners):
    """원본 이미지 ROI에서 Canny 엣지 검출"""
    pts = np.array(corners, dtype=np.int32)
    roi_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.fillPoly(roi_mask, [pts], 255)
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.bitwise_and(edges, roi_mask)
    
    return edges


def detect_lines_hough(edges, min_length=30, max_gap=10, threshold=30):
    """HoughLinesP로 직선 검출"""
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold, minLineLength=min_length, maxLineGap=max_gap)
    
    detected = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx, dy = x2 - x1, y2 - y1
            angle = math.degrees(math.atan2(dy, dx))
            length = math.sqrt(dx**2 + dy**2)
            detected.append(DetectedLine(p1=(x1, y1), p2=(x2, y2), angle=angle, length=length))
    
    return detected


def classify_line_type(line: DetectedLine, angle_threshold: float = 15) -> str:
    """라인 타입 분류 (수평/수직/대각)"""
    angle = abs(line.angle)
    
    if angle <= angle_threshold or angle >= (180 - angle_threshold):
        return 'horizontal'
    elif abs(angle - 90) <= angle_threshold or abs(angle + 90) <= angle_threshold:
        return 'vertical'
    else:
        return 'diagonal'


def classify_lines_by_court_spec(lines: List[DetectedLine], 
                                  calibration: CourtCalibration) -> List[DetectedLine]:
    """
    코트 규격 기반 라인 분류
    - 하드코딩된 비율 대신 실제 코트 규격(미터) 사용
    """
    line_positions = COURT_SPEC['line_positions']
    tolerance = calibration.tolerance_meters
    
    for line in lines:
        # 1. 라인 타입 분류 (수평/수직)
        line.line_type = classify_line_type(line)
        
        # 2. 픽셀 → 미터 변환
        x_meters, y_meters = calibration.pixels_to_meters(line.x_center, line.y_center)
        
        # 3. 카테고리 분류
        if line.line_type == 'vertical':
            # 수직선: X 좌표 기준으로 분류
            best_match = None
            min_distance = float('inf')
            
            for category in ['sideline_left_doubles', 'sideline_left_singles', 
                           'center', 'sideline_right_singles', 'sideline_right_doubles']:
                ref_x = line_positions[category]
                distance = abs(x_meters - ref_x)
                
                if distance < min_distance and distance < tolerance:
                    min_distance = distance
                    best_match = category
            
            if best_match:
                line.category = best_match
                line.distance_to_ref = min_distance
            else:
                line.category = 'vertical_other'
                
        elif line.line_type == 'horizontal':
            # 수평선: Y 좌표 기준으로 분류
            best_match = None
            min_distance = float('inf')
            
            for category in ['net', 'short_service', 'long_service', 'baseline']:
                ref_y = line_positions[category]
                distance = abs(y_meters - ref_y)
                
                if distance < min_distance and distance < tolerance:
                    min_distance = distance
                    best_match = category
            
            if best_match:
                line.category = best_match
                line.distance_to_ref = min_distance
            else:
                line.category = 'horizontal_other'
        else:
            line.category = 'diagonal_other'
    
    return lines


def merge_lines_by_category(lines: List[DetectedLine], 
                            calibration: CourtCalibration) -> List[DetectedLine]:
    """유사한 라인 병합"""
    groups = {}
    for line in lines:
        cat = line.category or 'unknown'
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(line)
    
    merged = []
    horizontal_categories = ['net', 'short_service', 'long_service', 'baseline', 'horizontal_other']
    
    # 병합 임계값 (픽셀)
    threshold_x = calibration.tolerance_pixels_x
    threshold_y = calibration.tolerance_pixels_y
    
    for cat, group in groups.items():
        if not group:
            continue
        
        is_horizontal = cat in horizontal_categories
        
        if is_horizontal:
            group.sort(key=lambda l: l.y_center)
            threshold = threshold_y
        else:
            group.sort(key=lambda l: l.x_center)
            threshold = threshold_x
        
        clusters = [[group[0]]]
        for line in group[1:]:
            if is_horizontal:
                dist = abs(line.y_center - clusters[-1][-1].y_center)
            else:
                dist = abs(line.x_center - clusters[-1][-1].x_center)
            
            if dist < threshold:
                clusters[-1].append(line)
            else:
                clusters.append([line])
        
        for cluster in clusters:
            best = max(cluster, key=lambda l: l.length)
            merged.append(best)
    
    return merged


def extend_center_line(lines: List[DetectedLine], 
                       calibration: CourtCalibration) -> List[DetectedLine]:
    """센터라인을 숏서비스~베이스라인까지 연장"""
    result = []
    center_found = False
    
    short_service_y = calibration.meters_to_pixels(0, COURT_SPEC['short_service'])[1]
    baseline_y = calibration.meters_to_pixels(0, COURT_SPEC['half_length'])[1]
    
    for line in lines:
        if line.category == 'center' and not center_found:
            x = line.x_center
            new_line = DetectedLine(
                p1=(int(x), int(short_service_y)),
                p2=(int(x), int(baseline_y)),
                angle=90.0, length=baseline_y - short_service_y,
                line_type='vertical', category='center'
            )
            result.append(new_line)
            center_found = True
        elif line.category != 'center':
            result.append(line)
    
    return result


def extend_sidelines_to_boundaries(lines: List[DetectedLine], 
                                    calibration: CourtCalibration) -> List[DetectedLine]:
    """사이드라인을 경계까지 연장"""
    result = []
    
    sideline_categories = [
        'sideline_left_doubles', 'sideline_left_singles',
        'sideline_right_doubles', 'sideline_right_singles'
    ]
    
    sidelines = [l for l in lines if l.category in sideline_categories]
    other_lines = [l for l in lines if l.category not in sideline_categories]
    
    for sideline in sidelines:
        dx = sideline.p2[0] - sideline.p1[0]
        dy = sideline.p2[1] - sideline.p1[1]
        
        if abs(dy) > 1e-10:
            t_top = -sideline.p1[1] / dy
            x_top = sideline.p1[0] + t_top * dx
            
            t_bottom = (calibration.warped_height - sideline.p1[1]) / dy
            x_bottom = sideline.p1[0] + t_bottom * dx
            
            x_top = max(0, min(calibration.warped_width, x_top))
            x_bottom = max(0, min(calibration.warped_width, x_bottom))
            
            extended = DetectedLine(
                p1=(int(x_top), 0), p2=(int(x_bottom), calibration.warped_height),
                angle=sideline.angle, length=calibration.warped_height,
                line_type='vertical', category=sideline.category
            )
            result.append(extended)
    
    result.extend(other_lines)
    return result


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
    'net': (0, 165, 255),              # Orange
    'baseline': (0, 255, 0),            # Green
    'short_service': (0, 255, 255),     # Yellow
    'long_service': (255, 255, 0),      # Cyan
    'center': (255, 0, 0),              # Blue
    'sideline_left_doubles': (255, 0, 255),    # Magenta
    'sideline_right_doubles': (255, 0, 255),
    'sideline_left_singles': (255, 150, 255),  # Light Pink
    'sideline_right_singles': (255, 150, 255),
}


def draw_lines(image: np.ndarray, lines: List[DetectedLine]) -> np.ndarray:
    """라인 시각화"""
    result = image.copy()
    
    for line in lines:
        if line.category not in COLORS:
            continue
        color = COLORS[line.category]
        cv2.line(result, line.p1, line.p2, color, 3)
        
        mid = line.midpoint
        label = line.category.replace('sideline_', '').replace('_', ' ')
        cv2.putText(result, label, (int(mid[0]) + 5, int(mid[1]) - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    return result


def draw_legend(image: np.ndarray) -> np.ndarray:
    """레전드"""
    result = image.copy()
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


def draw_court_reference(image: np.ndarray, calibration: CourtCalibration) -> np.ndarray:
    """코트 규격 기준선 시각화 (디버그용)"""
    result = image.copy()
    
    # 기준선 위치 (미터 → 픽셀)
    line_positions = COURT_SPEC['line_positions']
    
    # 수직선 기준
    for name in ['sideline_left_doubles', 'sideline_left_singles', 'center', 
                 'sideline_right_singles', 'sideline_right_doubles']:
        x_meters = line_positions[name]
        x_pixels = calibration.meters_to_pixels(x_meters, 0)[0]
        cv2.line(result, (x_pixels, 0), (x_pixels, calibration.warped_height), (100, 100, 100), 1)
        cv2.putText(result, f"{x_meters:.2f}m", (x_pixels + 2, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1)
    
    # 수평선 기준
    for name in ['net', 'short_service', 'long_service', 'baseline']:
        y_meters = line_positions[name]
        y_pixels = calibration.meters_to_pixels(0, y_meters)[1]
        cv2.line(result, (0, y_pixels), (calibration.warped_width, y_pixels), (100, 100, 100), 1)
        cv2.putText(result, f"{y_meters:.2f}m", (5, y_pixels - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1)
    
    return result


def draw_calibration_info(image: np.ndarray, calibration: CourtCalibration) -> np.ndarray:
    """캘리브레이션 정보 표시"""
    result = image.copy()
    
    info_lines = [
        f"Court Spec: {COURT_SPEC['width_doubles']}m x {COURT_SPEC['half_length']}m",
        f"Pixels/meter X: {calibration.pixels_per_meter_x:.1f}",
        f"Pixels/meter Y: {calibration.pixels_per_meter_y:.1f}",
        f"Tolerance: {calibration.tolerance_meters*100:.0f}cm",
    ]
    
    y = image.shape[0] - 20 - 20 * len(info_lines)
    for text in info_lines:
        cv2.putText(result, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        y += 20
    
    return result


def create_comparison_image(warped_v3: np.ndarray, warped_v4: np.ndarray, 
                            calibration: CourtCalibration) -> np.ndarray:
    """v3(하드코딩) vs v4(규격기반) 비교 이미지"""
    h, w = warped_v3.shape[:2]
    
    # 좌우 배치
    comparison = np.zeros((h, w * 2 + 20, 3), dtype=np.uint8)
    comparison[:, :w] = warped_v3
    comparison[:, w+20:] = warped_v4
    
    # 라벨
    cv2.putText(comparison, "v3: Hardcoded Ratios", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(comparison, "v4: Court Spec Based", (w + 30, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    return comparison


# ============================================================
# 메인 함수
# ============================================================

def load_json_config(json_path):
    """JSON 설정 파일 로드"""
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def process_test_case(test_case, base_output_dir="."):
    """개별 테스트 케이스 처리"""
    name = test_case.get('name', 'unknown')
    image_path = test_case.get('image_path')
    area = test_case.get('area')
    description = test_case.get('description', '')
    
    # 이미지 경로 확인
    if not os.path.exists(image_path):
        print(f"[ERROR] Image not found: {image_path}")
        return False
    
    # area 좌표 확인
    if not area or len(area) != 4:
        print(f"[ERROR] Area must have 4 points. Current: {len(area) if area else 0}")
        return False
    
    # area를 corners로 변환
    corners = [[int(p[0]), int(p[1])] for p in area]
    
    print(f"\n{'='*60}")
    print(f"[INFO] Processing: {name}")
    print(f"[INFO] Description: {description}")
    print(f"[INFO] Image: {image_path}")
    print(f"[INFO] Corners: {corners}")
    print(f"{'='*60}")
    
    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        print(f"[ERROR] Failed to load: {image_path}")
        return False
    
    print(f"[INFO] Original image: {image.shape}")
    
    # 출력 디렉토리 생성
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    output_dir = os.path.join(base_output_dir, f"court_lines_v5_{name}_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    print(f"[INFO] Output: {output_dir}")
    
    # 코트 규격 출력
    print(f"\n[Court Specification]")
    print(f"  Width (doubles): {COURT_SPEC['width_doubles']}m")
    print(f"  Half length: {COURT_SPEC['half_length']}m")
    print(f"  Singles offset: {COURT_SPEC['singles_offset']}m")
    print(f"  Short service: {COURT_SPEC['short_service']}m from net")
    print(f"  Long service: {COURT_SPEC['long_service']}m from net")
    
    cv2.imwrite(os.path.join(output_dir, "00_original.jpg"), image)
    
    # Step 1: 원본에서 엣지 검출
    print("\n[Step 1] Canny Edge Detection (Original)")
    edges_original = detect_edges_in_roi(image, corners)
    cv2.imwrite(os.path.join(output_dir, "01_canny_original.jpg"), edges_original)
    
    # Step 2: Bird's Eye View 변환
    print("\n[Step 2] Perspective Transform")
    edges_warped, M, M_inv = perspective_transform(
        cv2.cvtColor(edges_original, cv2.COLOR_GRAY2BGR), corners
    )
    edges_warped_gray = cv2.cvtColor(edges_warped, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(os.path.join(output_dir, "02_edges_warped.jpg"), edges_warped_gray)
    
    warped_h, warped_w = edges_warped_gray.shape[:2]
    print(f"  Warped size: {warped_w} x {warped_h}")
    
    image_warped, _, _ = perspective_transform(image, corners)
    cv2.imwrite(os.path.join(output_dir, "02b_image_warped.jpg"), image_warped)
    
    # Step 2.5: 캘리브레이션 생성
    print("\n[Step 2.5] Create Calibration")
    calibration = CourtCalibration.from_warped_size(warped_w, warped_h, tolerance=0.20)
    print(f"  Pixels per meter (X): {calibration.pixels_per_meter_x:.2f}")
    print(f"  Pixels per meter (Y): {calibration.pixels_per_meter_y:.2f}")
    print(f"  Tolerance: {calibration.tolerance_meters}m = {calibration.tolerance_pixels_x:.1f}px (X), {calibration.tolerance_pixels_y:.1f}px (Y)")
    
    # 코트 기준선 시각화
    reference_image = draw_court_reference(image_warped, calibration)
    reference_image = draw_calibration_info(reference_image, calibration)
    cv2.imwrite(os.path.join(output_dir, "02c_court_reference.jpg"), reference_image)
    
    # Step 3: Hough Line 검출
    print("\n[Step 3] Hough Line Detection")
    detected_lines = detect_lines_hough(edges_warped_gray, min_length=50, max_gap=20, threshold=30)
    print(f"  Detected: {len(detected_lines)} lines")
    
    # Step 4: 라인 분류 (코트 규격 기반)
    print("\n[Step 4] Line Classification (Court Spec Based)")
    detected_lines = classify_lines_by_court_spec(detected_lines, calibration)
    
    cat_counts = {}
    for line in detected_lines:
        cat_counts[line.category] = cat_counts.get(line.category, 0) + 1
    print(f"  Categories: {cat_counts}")
    
    # Step 5: 라인 병합
    print("\n[Step 5] Line Merging")
    merged_lines = merge_lines_by_category(detected_lines, calibration)
    
    main_categories = [
        'net', 'short_service', 'long_service', 'baseline', 'center',
        'sideline_left_doubles', 'sideline_left_singles',
        'sideline_right_doubles', 'sideline_right_singles'
    ]
    main_lines = [l for l in merged_lines if l.category in main_categories]
    print(f"  Main court lines: {len(main_lines)}")
    
    # Step 5.5: 센터라인 연장
    print("\n[Step 5.5] Extend Center Line")
    main_lines = extend_center_line(main_lines, calibration)
    
    # Step 5.6: 사이드라인 연장
    print("\n[Step 5.6] Extend Sidelines")
    main_lines = extend_sidelines_to_boundaries(main_lines, calibration)
    
    # 최종 라인 출력 (미터 단위 포함)
    print("\n[Final Lines with Court Coordinates]")
    for line in main_lines:
        x_m, y_m = calibration.pixels_to_meters(line.x_center, line.y_center)
        print(f"  - {line.category}: ({x_m:.2f}m, {y_m:.2f}m)")
    
    # 시각화 (warped)
    main_warped = draw_lines(image_warped, main_lines)
    main_warped = draw_legend(main_warped)
    main_warped = draw_calibration_info(main_warped, calibration)
    cv2.imwrite(os.path.join(output_dir, "04_main_lines_warped.jpg"), main_warped)
    
    # Step 6: 원본 좌표로 역변환
    print("\n[Step 6] Transform to Original")
    original_lines = transform_lines_to_original(main_lines, M_inv)
    
    result_original = draw_lines(image, original_lines)
    result_original = draw_legend(result_original)
    cv2.imwrite(os.path.join(output_dir, "05_result_original.jpg"), result_original)
    
    # 결과 JSON (미터 단위 포함)
    results = {
        'test_case': {
            'name': name,
            'description': description,
            'image_path': image_path,
        },
        'court_spec': COURT_SPEC,
        'calibration': {
            'warped_size': [warped_w, warped_h],
            'pixels_per_meter_x': float(calibration.pixels_per_meter_x),
            'pixels_per_meter_y': float(calibration.pixels_per_meter_y),
            'tolerance_meters': float(calibration.tolerance_meters),
        },
        'detected_lines': [
            {
                'category': l.category,
                'x_meters': float(calibration.pixels_to_meters(l.x_center, 0)[0]),
                'y_meters': float(calibration.pixels_to_meters(0, l.y_center)[1]),
                'warped_coords': {'p1': [int(l.p1[0]), int(l.p1[1])], 'p2': [int(l.p2[0]), int(l.p2[1])]},
            }
            for l in main_lines
        ]
    }
    with open(os.path.join(output_dir, "results.json"), 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[INFO] Results saved to {output_dir}")
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='배드민턴 코트 라인 검출 v5 - JSON 설정 파일 기반 (코트 규격 기반 동적 분류)'
    )
    parser.add_argument(
        'json_path',
        type=str,
        help='JSON 설정 파일 경로 (이미지 경로와 area 좌표 포함)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='.',
        help='출력 디렉토리 (기본값: 현재 디렉토리)'
    )
    
    args = parser.parse_args()
    
    # JSON 파일 경로 확인
    json_path = args.json_path
    if not os.path.exists(json_path):
        print(f"[ERROR] JSON file not found: {json_path}")
        return
    
    print(f"[INFO] Loading JSON config: {json_path}")
    
    # JSON 파일 로드
    try:
        config = load_json_config(json_path)
    except Exception as e:
        print(f"[ERROR] Failed to load JSON: {e}")
        return
    
    # test_cases 처리
    test_cases = config.get('test_cases', [])
    if not test_cases:
        print("[ERROR] No test_cases found in JSON file")
        return
    
    print(f"[INFO] Found {len(test_cases)} test case(s)")
    
    # 각 테스트 케이스 처리
    success_count = 0
    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n\n{'#'*60}")
        print(f"# Processing Test Case {idx}/{len(test_cases)}")
        print(f"{'#'*60}")
        
        if process_test_case(test_case, args.output):
            success_count += 1
    
    # 결과 요약
    print(f"\n\n{'='*60}")
    print(f"[SUMMARY] Completed: {success_count}/{len(test_cases)} test cases")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

# python courtline_detector_v5.py  /mnt/b/cd_p/bmt_demo/stage1_courtdetection/niceangle_wide_halfcourt.json