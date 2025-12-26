"""
Badminton Court Edge Detection Pipeline v2
==========================================
사용자 입력 4개 코너 좌표를 Ground Truth로 활용하여
코트 라인을 정확하게 정의하고 시각화

배드민턴 반코트 구조:
- 4개 코너: TL, TR, BR, BL (단식 롱서브라인 기준 외곽)
- 내부 라인: 표준 코트 비율로 계산
"""

import cv2
import numpy as np
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from pathlib import Path


@dataclass
class CourtDimensions:
    """배드민턴 코트 실제 치수 (미터)"""
    # 전체 코트
    full_length: float = 13.4       # 전체 길이
    doubles_width: float = 6.1      # 복식 폭
    singles_width: float = 5.18     # 단식 폭
    
    # 반코트 기준 (네트에서)
    half_length: float = 6.7        # 반코트 길이
    short_service: float = 1.98     # 숏서비스 라인 (네트에서)
    long_service_doubles: float = 0.76  # 복식 롱서비스 (베이스라인에서)
    
    # 계산된 값
    @property
    def alley_width(self) -> float:
        """복식 앨리 폭"""
        return (self.doubles_width - self.singles_width) / 2  # 0.46m
    
    @property
    def half_singles_width(self) -> float:
        """단식 코트 절반 폭"""
        return self.singles_width / 2  # 2.59m


@dataclass
class CourtLine:
    """코트 라인 정의"""
    name: str
    p1: Tuple[float, float]  # 시작점 (x, y)
    p2: Tuple[float, float]  # 끝점 (x, y)
    line_type: str           # 'baseline', 'sideline', 'service', 'center'
    color: Tuple[int, int, int] = (255, 255, 255)  # BGR
    
    @property
    def angle(self) -> float:
        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        return np.degrees(np.arctan2(dy, dx))
    
    @property
    def length(self) -> float:
        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        return np.sqrt(dx**2 + dy**2)


class CourtLineDetector:
    """메타데이터 기반 코트 라인 검출기"""
    
    # 라인 타입별 색상 (BGR)
    LINE_COLORS = {
        'baseline': (0, 255, 0),        # Green - 베이스라인
        'sideline': (255, 0, 255),      # Magenta - 사이드라인
        'service': (0, 255, 255),       # Yellow - 서비스라인 (숏서비스)
        'center': (255, 0, 0),          # Blue - 센터라인
    }
    
    LINE_LABELS = {
        'baseline': 'Baseline (Green)',
        'sideline': 'Sideline (Magenta)', 
        'service': 'Short Service Line (Yellow)',
        'center': 'Center Line (Blue)',
    }
    
    def __init__(self):
        self.dims = CourtDimensions()
        self.court_lines: List[CourtLine] = []
        
    def create_output_dir(self, base_path: str = ".") -> str:
        """타임스탬프 기반 출력 디렉토리 생성"""
        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        output_dir = os.path.join(base_path, timestamp)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def compute_court_lines_from_corners(self, corners: List[List[int]]) -> List[CourtLine]:
        """
        4개 코너 좌표로부터 모든 코트 라인 계산
        
        Args:
            corners: [[TL], [TR], [BR], [BL]] - 반코트 외곽 (단식 롱서브라인 기준)
            
        입력 좌표 해석:
        - TL, TR: 숏서비스 라인과 사이드라인의 교점
        - BL, BR: 베이스라인(롱서브라인)과 사이드라인의 교점
        
        반코트 구조 (카메라 뷰):
        
        TL -------- TR   (숏서비스 라인)
        |     |     |
        |     |     |
        |     |     |
        BL -------- BR   (베이스라인/롱서브라인)
        """
        tl = np.array(corners[0], dtype=np.float32)
        tr = np.array(corners[1], dtype=np.float32)
        br = np.array(corners[2], dtype=np.float32)
        bl = np.array(corners[3], dtype=np.float32)
        
        lines = []
        
        # ============================================
        # 1. 외곽 4변 (사용자 입력 좌표 = 실제 코트 라인)
        # ============================================
        
        # 상단: 숏서비스 라인 - TL to TR
        lines.append(CourtLine(
            name="Short Service Line",
            p1=tuple(tl), p2=tuple(tr),
            line_type='service',
            color=self.LINE_COLORS['service']
        ))
        
        # 하단: 베이스라인 (롱서브라인) - BL to BR
        lines.append(CourtLine(
            name="Baseline (Long Service)",
            p1=tuple(bl), p2=tuple(br),
            line_type='baseline',
            color=self.LINE_COLORS['baseline']
        ))
        
        # 좌측 사이드라인 - TL to BL
        lines.append(CourtLine(
            name="Left Sideline",
            p1=tuple(tl), p2=tuple(bl),
            line_type='sideline',
            color=self.LINE_COLORS['sideline']
        ))
        
        # 우측 사이드라인 - TR to BR
        lines.append(CourtLine(
            name="Right Sideline",
            p1=tuple(tr), p2=tuple(br),
            line_type='sideline',
            color=self.LINE_COLORS['sideline']
        ))
        
        # ============================================
        # 2. 내부 라인: 센터라인
        # ============================================
        
        # 센터라인: 숏서비스 라인 중점 ~ 베이스라인 중점
        center_top = (tl + tr) / 2
        center_bottom = (bl + br) / 2
        
        lines.append(CourtLine(
            name="Center Line",
            p1=tuple(center_top), p2=tuple(center_bottom),
            line_type='center',
            color=self.LINE_COLORS['center']
        ))
        
        self.court_lines = lines
        return lines
    
    def interpolate_point(self, p1: np.ndarray, p2: np.ndarray, 
                          ratio: float) -> np.ndarray:
        """두 점 사이를 비율로 보간"""
        return p1 + ratio * (p2 - p1)
    
    def draw_court_lines(self, image: np.ndarray, 
                         lines: List[CourtLine],
                         thickness: int = 3) -> np.ndarray:
        """코트 라인 그리기"""
        result = image.copy()
        
        for line in lines:
            p1 = tuple(map(int, line.p1))
            p2 = tuple(map(int, line.p2))
            cv2.line(result, p1, p2, line.color, thickness)
            
        return result
    
    def draw_corners(self, image: np.ndarray, 
                     corners: List[List[int]]) -> np.ndarray:
        """코너 포인트 표시"""
        result = image.copy()
        labels = ['TL', 'TR', 'BR', 'BL']
        
        for pt, label in zip(corners, labels):
            cv2.circle(result, tuple(pt), 10, (0, 0, 255), -1)
            cv2.putText(result, label, (pt[0] + 15, pt[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        return result
    
    def draw_legend(self, image: np.ndarray, 
                    line_counts: Dict[str, int]) -> np.ndarray:
        """좌상단 레전드"""
        result = image.copy()
        
        legend_height = 35 * len(self.LINE_LABELS) + 25
        legend_width = 280
        
        # 배경
        overlay = result.copy()
        cv2.rectangle(overlay, (10, 10), (legend_width, legend_height), 
                     (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.8, result, 0.2, 0, result)
        cv2.rectangle(result, (10, 10), (legend_width, legend_height), 
                     (200, 200, 200), 2)
        
        y_offset = 40
        for line_type, label in self.LINE_LABELS.items():
            color = self.LINE_COLORS[line_type]
            count = line_counts.get(line_type, 0)
            
            # 색상 박스
            cv2.rectangle(result, (20, y_offset - 15), (50, y_offset + 5), 
                         color, -1)
            
            # 텍스트
            text = f"{label}: {count}"
            cv2.putText(result, text, (60, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            y_offset += 35
        
        return result
    
    def create_polygon_visualization(self, image: np.ndarray,
                                      corners: List[List[int]],
                                      lines: List[CourtLine]) -> np.ndarray:
        """
        최종 폴리곤 형태 시각화
        - 코트 영역 반투명 오버레이
        - 각 엣지별 다른 색상
        - 레전드 포함
        """
        result = image.copy()
        
        # 1. 코트 영역 반투명 오버레이
        pts = np.array(corners, dtype=np.int32)
        overlay = result.copy()
        cv2.fillPoly(overlay, [pts], (100, 100, 100))
        cv2.addWeighted(overlay, 0.3, result, 0.7, 0, result)
        
        # 2. 코트 라인 그리기
        result = self.draw_court_lines(result, lines, thickness=4)
        
        # 3. 코너 표시
        result = self.draw_corners(result, corners)
        
        # 4. 라인 타입별 카운트
        line_counts = {}
        for line in lines:
            line_counts[line.line_type] = line_counts.get(line.line_type, 0) + 1
        
        # 5. 레전드
        result = self.draw_legend(result, line_counts)
        
        return result
    
    def detect_additional_lines_canny(self, image: np.ndarray,
                                       corners: List[List[int]],
                                       known_lines: List[CourtLine]) -> List[CourtLine]:
        """
        Canny + Hough로 추가 라인 검출 (선택적)
        이미 정의된 라인과 중복되지 않는 라인만 반환
        """
        # ROI 마스크 생성
        pts = np.array(corners, dtype=np.int32)
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        
        # 전처리
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        
        # 화이트 마스킹
        hls = cv2.cvtColor(image, cv2.COLOR_BGR2HLS)
        l_channel = hls[:, :, 1]
        white_mask = ((l_channel >= 150) & (l_channel <= 255)).astype(np.uint8) * 255
        
        # ROI 적용
        white_mask = cv2.bitwise_and(white_mask, mask)
        masked = cv2.bitwise_and(blurred, blurred, mask=white_mask)
        
        # Canny
        edges = cv2.Canny(masked, 30, 100)
        
        return edges, masked
    
    def process(self, image_path: str, corners: List[List[int]], 
                output_dir: str = None) -> Dict:
        """
        전체 파이프라인 실행
        """
        if output_dir is None:
            output_dir = self.create_output_dir()
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        print(f"[INFO] Output directory: {output_dir}")
        
        # 이미지 로드
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        print(f"[INFO] Loaded image: {image.shape}")
        print(f"[INFO] Court corners: {corners}")
        
        # Step 0: 원본 이미지 저장
        cv2.imwrite(os.path.join(output_dir, "00_original.jpg"), image)
        
        # Step 1: 코너 표시
        img_with_corners = self.draw_corners(image, corners)
        cv2.imwrite(os.path.join(output_dir, "01_corners.jpg"), img_with_corners)
        
        # Step 2: 코트 라인 계산
        lines = self.compute_court_lines_from_corners(corners)
        print(f"[INFO] Computed {len(lines)} court lines")
        
        for line in lines:
            print(f"  - {line.name}: {line.line_type}")
        
        # Step 3: 코트 라인만 그리기
        img_with_lines = self.draw_court_lines(image, lines, thickness=3)
        cv2.imwrite(os.path.join(output_dir, "02_court_lines.jpg"), img_with_lines)
        
        # Step 4: Canny 엣지 (참고용)
        edges, masked = self.detect_additional_lines_canny(image, corners, lines)
        cv2.imwrite(os.path.join(output_dir, "03_canny_edges.jpg"), edges)
        cv2.imwrite(os.path.join(output_dir, "03_white_masked.jpg"), masked)
        
        # Step 5: 최종 폴리곤 시각화
        final_result = self.create_polygon_visualization(image, corners, lines)
        cv2.imwrite(os.path.join(output_dir, "04_final_polygon.jpg"), final_result)
        
        # Step 6: 엣지 위에 라인 오버레이 (요청하신 형태)
        edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        edges_with_lines = self.draw_court_lines(edges_colored, lines, thickness=3)
        
        line_counts = {}
        for line in lines:
            line_counts[line.line_type] = line_counts.get(line.line_type, 0) + 1
        edges_with_lines = self.draw_legend(edges_with_lines, line_counts)
        cv2.imwrite(os.path.join(output_dir, "05_edges_with_lines.jpg"), edges_with_lines)
        
        # 결과 JSON
        results = {
            'output_dir': output_dir,
            'corners': corners,
            'lines': [
                {
                    'name': l.name,
                    'type': l.line_type,
                    'p1': [float(l.p1[0]), float(l.p1[1])],
                    'p2': [float(l.p2[0]), float(l.p2[1])],
                    'length': float(l.length),
                    'angle': float(l.angle)
                }
                for l in lines
            ],
            'line_counts': line_counts
        }
        
        with open(os.path.join(output_dir, "detection_results.json"), 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"[INFO] Processing complete")
        print(f"[INFO] Line counts: {line_counts}")
        
        return results


def main():
    """메인 실행"""
    # JSON 설정
    config = {
        "test_cases": [
            {
                "name": "session_46c389d2",
                "image_path": "/mnt/b/cd_p/bmt_demo/stage1_courtdetection/46c389d2-feac-4204-84b8-052aebf76d5c_result.jpg",
                "area": [
                    [977, 828],   # TL - 숏서비스라인 좌측
                    [1751, 826],  # TR - 숏서비스라인 우측
                    [2691, 1410], # BR - 베이스라인 우측
                    [8, 1418]     # BL - 베이스라인 좌측
                ],
                "description": "실제 세션 이미지 - 정면 촬영"
            }
        ]
    }
    
    detector = CourtLineDetector()
    
    for test_case in config["test_cases"]:
        print(f"\n{'='*60}")
        print(f"Processing: {test_case['name']}")
        print(f"Description: {test_case['description']}")
        print(f"{'='*60}")
        
        try:
            results = detector.process(
                image_path=test_case["image_path"],
                corners=test_case["area"]
            )
            
            print(f"\n[RESULTS]")
            print(f"  Total lines: {len(results['lines'])}")
            for lt, count in results['line_counts'].items():
                print(f"    - {lt}: {count}")
                
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()