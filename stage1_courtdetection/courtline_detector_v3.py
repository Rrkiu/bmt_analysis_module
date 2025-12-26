"""
배드민턴 코트 라인 검출 v3
========================
- Edge First 방식 (원본에서 엣지 검출 후 변환)
- 복식 롱서비스 라인 검출
- 센터라인 연장 (숏서비스~베이스라인)
- 사이드라인 연장 및 경계 클리핑
"""

import cv2
import numpy as np
import json
import os
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional
import math


@dataclass
class DetectedLine:
    p1: Tuple[int, int]
    p2: Tuple[int, int]
    angle: float
    length: float
    line_type: Optional[str] = None
    category: Optional[str] = None
    
    @property
    def midpoint(self) -> Tuple[float, float]:
        return ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)
    
    @property
    def y_center(self) -> float:
        return (self.p1[1] + self.p2[1]) / 2
    
    @property
    def x_center(self) -> float:
        return (self.p1[0] + self.p2[0]) / 2


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
        court_ratio = 6.7 / 5.18
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


def classify_lines_in_warped(lines, warped_width, warped_height, angle_threshold=15):
    """Bird's Eye View에서 라인 분류"""
    for line in lines:
        angle = abs(line.angle)
        
        if angle <= angle_threshold or angle >= (180 - angle_threshold):
            line.line_type = 'horizontal'
            y_ratio = line.y_center / warped_height
            
            if y_ratio < 0.05:
                line.category = 'net'
            elif 0.15 < y_ratio < 0.50:
                line.category = 'short_service'
            elif 0.83 < y_ratio < 0.92:
                line.category = 'long_service'
            elif y_ratio > 0.95:
                line.category = 'baseline'
            else:
                line.category = 'horizontal_other'
                
        elif abs(angle - 90) <= angle_threshold or abs(angle + 90) <= angle_threshold:
            line.line_type = 'vertical'
            x_ratio = line.x_center / warped_width
            
            if 0.40 < x_ratio < 0.60:
                line.category = 'center'
            elif x_ratio < 0.15:
                line.category = 'sideline_left'
            elif x_ratio > 0.85:
                line.category = 'sideline_right'
            else:
                line.category = 'vertical_other'
        else:
            line.line_type = 'diagonal'
            line.category = 'diagonal_other'
    
    return lines


def merge_lines_by_category(lines, threshold=30):
    """유사한 라인 병합"""
    groups = {}
    for line in lines:
        cat = line.category or 'unknown'
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(line)
    
    merged = []
    for cat, group in groups.items():
        if not group:
            continue
        
        if cat in ['net', 'short_service', 'long_service', 'baseline', 'horizontal_other']:
            group.sort(key=lambda l: l.y_center)
        else:
            group.sort(key=lambda l: l.x_center)
        
        clusters = [[group[0]]]
        for line in group[1:]:
            if cat in ['net', 'short_service', 'long_service', 'baseline', 'horizontal_other']:
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


def extend_center_line(lines, short_service_y, baseline_y):
    """센터라인을 숏서비스~베이스라인까지 연장"""
    result = []
    center_found = False
    
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


def extend_sidelines_to_boundaries(lines, warped_width, warped_height):
    """
    사이드라인을 경계(네트~베이스라인)까지 연장
    - 단식/복식 사이드라인 모두 유지
    - 각 세그먼트의 기울기로 연장
    """
    result = []
    
    left_sidelines = [l for l in lines if l.category == 'sideline_left']
    right_sidelines = [l for l in lines if l.category == 'sideline_right']
    other_lines = [l for l in lines if l.category not in ['sideline_left', 'sideline_right']]
    
    # 좌측 사이드라인들 각각 연장
    for sideline in left_sidelines:
        dx = sideline.p2[0] - sideline.p1[0]
        dy = sideline.p2[1] - sideline.p1[1]
        
        if abs(dy) > 1e-10:
            # y=0 (상단)과의 교점
            t_top = -sideline.p1[1] / dy
            x_top = sideline.p1[0] + t_top * dx
            
            # y=warped_height (하단)과의 교점
            t_bottom = (warped_height - sideline.p1[1]) / dy
            x_bottom = sideline.p1[0] + t_bottom * dx
            
            # 경계 클리핑
            x_top = max(0, min(warped_width, x_top))
            x_bottom = max(0, min(warped_width, x_bottom))
            
            extended = DetectedLine(
                p1=(int(x_top), 0), p2=(int(x_bottom), warped_height),
                angle=sideline.angle, length=warped_height,
                line_type='vertical', category='sideline_left'
            )
            result.append(extended)
            print(f"    Left sideline extended: x_top={x_top:.1f}, x_bottom={x_bottom:.1f}")
    
    # 우측 사이드라인들 각각 연장
    for sideline in right_sidelines:
        dx = sideline.p2[0] - sideline.p1[0]
        dy = sideline.p2[1] - sideline.p1[1]
        
        if abs(dy) > 1e-10:
            t_top = -sideline.p1[1] / dy
            x_top = sideline.p1[0] + t_top * dx
            
            t_bottom = (warped_height - sideline.p1[1]) / dy
            x_bottom = sideline.p1[0] + t_bottom * dx
            
            x_top = max(0, min(warped_width, x_top))
            x_bottom = max(0, min(warped_width, x_bottom))
            
            extended = DetectedLine(
                p1=(int(x_top), 0), p2=(int(x_bottom), warped_height),
                angle=sideline.angle, length=warped_height,
                line_type='vertical', category='sideline_right'
            )
            result.append(extended)
            print(f"    Right sideline extended: x_top={x_top:.1f}, x_bottom={x_bottom:.1f}")
    
    result.extend(other_lines)
    return result


def transform_lines_to_original(lines, M_inv):
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


def draw_lines(image, lines):
    """라인 시각화"""
    result = image.copy()
    
    colors = {
        'net': (0, 165, 255),
        'baseline': (0, 255, 0),
        'short_service': (0, 255, 255),
        'long_service': (255, 255, 0),
        'center': (255, 0, 0),
        'sideline_left': (255, 0, 255),
        'sideline_right': (255, 0, 255),
    }
    
    for line in lines:
        if line.category not in colors:
            continue
        color = colors[line.category]
        cv2.line(result, line.p1, line.p2, color, 3)
        
        mid = line.midpoint
        cv2.putText(result, line.category, (int(mid[0]) + 5, int(mid[1]) - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    return result


def draw_legend(image):
    """레전드"""
    result = image.copy()
    items = [
        ('Net Line', (0, 165, 255)),
        ('Short Service', (0, 255, 255)),
        ('Long Service (Doubles)', (255, 255, 0)),
        ('Baseline', (0, 255, 0)),
        ('Center Line', (255, 0, 0)),
        ('Sideline', (255, 0, 255)),
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
    
    # area를 corners로 변환 (list of lists -> list of lists)
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
    
    # 출력 디렉토리 생성 (테스트 케이스별)
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    output_dir = os.path.join(base_output_dir, f"court_lines_{name}_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    print(f"[INFO] Output: {output_dir}")
    
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
    
    # Step 3: Hough Line 검출
    print("\n[Step 3] Hough Line Detection")
    detected_lines = detect_lines_hough(edges_warped_gray, min_length=50, max_gap=20, threshold=30)
    print(f"  Detected: {len(detected_lines)} lines")
    
    # Step 4: 라인 분류
    print("\n[Step 4] Line Classification")
    detected_lines = classify_lines_in_warped(detected_lines, warped_w, warped_h)
    
    cat_counts = {}
    for line in detected_lines:
        cat_counts[line.category] = cat_counts.get(line.category, 0) + 1
    print(f"  Categories: {cat_counts}")
    
    # Step 5: 라인 병합
    print("\n[Step 5] Line Merging")
    merged_lines = merge_lines_by_category(detected_lines)
    
    main_categories = ['net', 'short_service', 'long_service', 'baseline', 'center', 'sideline_left', 'sideline_right']
    main_lines = [l for l in merged_lines if l.category in main_categories]
    print(f"  Main court lines: {len(main_lines)}")
    
    # Step 5.5: 센터라인 연장
    print("\n[Step 5.5] Extend Center Line")
    short_service = next((l for l in main_lines if l.category == 'short_service'), None)
    baseline = next((l for l in main_lines if l.category == 'baseline'), None)
    
    if short_service and baseline:
        main_lines = extend_center_line(main_lines, short_service.y_center, baseline.y_center)
        print(f"  Extended from y={short_service.y_center:.1f} to y={baseline.y_center:.1f}")
    
    # Step 5.6: 사이드라인 연장
    print("\n[Step 5.6] Extend Sidelines")
    main_lines = extend_sidelines_to_boundaries(main_lines, warped_w, warped_h)
    
    # 최종 라인 출력
    print("\n[Final Lines]")
    for line in main_lines:
        print(f"  - {line.category}: p1={line.p1}, p2={line.p2}")
    
    # 시각화 (warped)
    main_warped = draw_lines(image_warped, main_lines)
    main_warped = draw_legend(main_warped)
    cv2.imwrite(os.path.join(output_dir, "04_main_lines_warped.jpg"), main_warped)
    
    # Step 6: 원본 좌표로 역변환
    print("\n[Step 6] Transform to Original")
    original_lines = transform_lines_to_original(main_lines, M_inv)
    
    result_original = draw_lines(image, original_lines)
    result_original = draw_legend(result_original)
    cv2.imwrite(os.path.join(output_dir, "05_result_original.jpg"), result_original)
    
    print(f"\n[INFO] Results saved to {output_dir}")
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='배드민턴 코트 라인 검출 v3 - JSON 설정 파일 기반'
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