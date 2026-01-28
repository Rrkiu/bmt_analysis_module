"""
코트 라인 검출 테스트 스크립트

워크플로우 (Option 1):
1. 사용자가 대략적인 4개 코너 지정
2. 해당 영역 내에서 정밀 라인 검출
3. 검출된 라인으로 코너 재계산
4. 사용자 확인 및 수정
5. 최종 캘리브레이션

테스트 알고리즘:
1. 색상 필터링 (흰색 라인)
2. Canny + Hough Transform
3. Adaptive Threshold
4. Combined (하이브리드)
"""

import cv2
import numpy as np
import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional


class CourtLineDetector:
    """코트 라인 검출기"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def load_test_case(self, config_path: str) -> Dict:
        """테스트 케이스 로드"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_roi_mask(self, image_shape: Tuple[int, int], corners: List[List[int]]) -> np.ndarray:
        """ROI 마스크 생성"""
        mask = np.zeros(image_shape[:2], dtype=np.uint8)
        pts = np.array(corners, dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
        return mask
    
    def visualize_roi(self, image: np.ndarray, corners: List[List[int]], 
                      test_name: str, algorithm: str = "roi") -> str:
        """ROI 영역 시각화"""
        vis = image.copy()
        pts = np.array(corners, dtype=np.int32)
        
        # ROI 폴리곤 그리기
        cv2.polylines(vis, [pts], True, (0, 255, 0), 2)
        
        # 코너 점 그리기
        labels = ['TL', 'TR', 'BR', 'BL']
        colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0)]
        for i, (corner, label, color) in enumerate(zip(corners, labels, colors)):
            cv2.circle(vis, tuple(corner), 8, color, -1)
            cv2.putText(vis, label, (corner[0] + 15, corner[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 저장
        filename = f"{test_name}_{algorithm}_roi.jpg"
        output_path = self.output_dir / filename
        cv2.imwrite(str(output_path), vis)
        print(f"✅ Saved: {filename}")
        return str(output_path)
    
    def method1_color_filter(self, image: np.ndarray, mask: Optional[np.ndarray],
                            test_name: str, use_roi: bool = True) -> Tuple[np.ndarray, List, float]:
        """
        방법 1: 색상 필터링 (흰색 라인 검출)
        
        Args:
            image: 원본 이미지
            mask: ROI 마스크 (use_roi=False면 무시)
            test_name: 테스트 이름
            use_roi: True면 ROI 영역만, False면 전체 이미지
            
        Returns:
            (white_mask, lines, elapsed_time)
        """
        start_time = time.time()
        
        scope = "roi" if use_roi else "full"
        print(f"\n🔍 Method 1: Color Filter [{scope.upper()}]")
        
        # ROI 적용 여부
        if use_roi and mask is not None:
            roi_image = cv2.bitwise_and(image, image, mask=mask)
        else:
            roi_image = image.copy()
        
        # HSV 변환
        hsv = cv2.cvtColor(roi_image, cv2.COLOR_BGR2HSV)
        
        # 흰색 범위 (밝기 높은 영역)
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # 노이즈 제거
        kernel = np.ones((3, 3), np.uint8)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)
        
        # 시각화 1: 색상 필터 결과
        vis1 = cv2.cvtColor(white_mask, cv2.COLOR_GRAY2BGR)
        filename1 = f"{test_name}_color_filter_{scope}_step1_white_mask.jpg"
        cv2.imwrite(str(self.output_dir / filename1), vis1)
        print(f"  ✅ Step 1: {filename1}")
        
        # Hough Line Transform
        lines = cv2.HoughLinesP(white_mask, 1, np.pi/180, threshold=50,
                               minLineLength=50, maxLineGap=10)
        
        # 시각화 2: 검출된 라인
        vis2 = image.copy()
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(vis2, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        filename2 = f"{test_name}_color_filter_{scope}_step2_detected_lines.jpg"
        cv2.imwrite(str(self.output_dir / filename2), vis2)
        
        elapsed_time = time.time() - start_time
        print(f"  ✅ Step 2: {filename2}")
        print(f"  ⏱️  Time: {elapsed_time:.3f}s")
        
        return white_mask, lines if lines is not None else [], elapsed_time
    
    def method2_canny_hough(self, image: np.ndarray, mask: Optional[np.ndarray],
                           test_name: str, use_roi: bool = True) -> Tuple[np.ndarray, List, float]:
        """
        방법 2: Canny Edge + Hough Transform
        
        Args:
            image: 원본 이미지
            mask: ROI 마스크 (use_roi=False면 무시)
            test_name: 테스트 이름
            use_roi: True면 ROI 영역만, False면 전체 이미지
            
        Returns:
            (edges, lines, elapsed_time)
        """
        start_time = time.time()
        scope = "roi" if use_roi else "full"
        print(f"\n🔍 Method 2: Canny Edge + Hough Transform [{scope.UPPER()}]")
        
        # ROI 적용 여부
        if use_roi and mask is not None:
            roi_image = cv2.bitwise_and(image, image, mask=mask)
        else:
            roi_image = image.copy()
        
        # 그레이스케일 변환
        gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
        
        # 가우시안 블러
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Canny 엣지 검출
        edges = cv2.Canny(blurred, 50, 150)
        
        # 시각화 1: Canny 엣지
        vis1 = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        filename1 = f"{test_name}_canny_hough_{scope}_step1_edges.jpg"
        cv2.imwrite(str(self.output_dir / filename1), vis1)
        print(f"  ✅ Step 1: {filename1}")
        
        # Hough Line Transform
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                               minLineLength=100, maxLineGap=20)
        
        # 시각화 2: 검출된 라인
        vis2 = image.copy()
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(vis2, (x1, y1), (x2, y2), (255, 0, 0), 2)
        
        filename2 = f"{test_name}_canny_hough_{scope}_step2_detected_lines.jpg"
        cv2.imwrite(str(self.output_dir / filename2), vis2)
        
        elapsed_time = time.time() - start_time
        print(f"  ✅ Step 2: {filename2}")
        print(f"  ⏱️  Time: {elapsed_time:.3f}s")
        
        return edges, lines if lines is not None else [], elapsed_time
    
    def method3_adaptive_threshold(self, image: np.ndarray, mask: Optional[np.ndarray],
                                   test_name: str, use_roi: bool = True) -> Tuple[np.ndarray, List, float]:
        """
        방법 3: Adaptive Threshold
        
        Args:
            image: 원본 이미지
            mask: ROI 마스크 (use_roi=False면 무시)
            test_name: 테스트 이름
            use_roi: True면 ROI 영역만, False면 전체 이미지
            
        Returns:
            (thresh_inv, lines, elapsed_time)
        """
        start_time = time.time()
        scope = "roi" if use_roi else "full"
        print(f"\n🔍 Method 3: Adaptive Threshold [{scope.upper()}]")
        
        # ROI 적용 여부
        if use_roi and mask is not None:
            roi_image = cv2.bitwise_and(image, image, mask=mask)
        else:
            roi_image = image.copy()
        
        # 그레이스케일 변환
        gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
        
        # Adaptive Threshold
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, 11, 2)
        
        # 반전 (흰색 라인이 검정색이 되도록)
        thresh_inv = cv2.bitwise_not(thresh)
        
        # 시각화 1: Threshold 결과
        vis1 = cv2.cvtColor(thresh_inv, cv2.COLOR_GRAY2BGR)
        filename1 = f"{test_name}_adaptive_threshold_{scope}_step1_binary.jpg"
        cv2.imwrite(str(self.output_dir / filename1), vis1)
        print(f"  ✅ Step 1: {filename1}")
        
        # Hough Line Transform
        lines = cv2.HoughLinesP(thresh_inv, 1, np.pi/180, threshold=60,
                               minLineLength=80, maxLineGap=15)
        
        # 시각화 2: 검출된 라인
        vis2 = image.copy()
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(vis2, (x1, y1), (x2, y2), (0, 0, 255), 2)
        
        filename2 = f"{test_name}_adaptive_threshold_{scope}_step2_detected_lines.jpg"
        cv2.imwrite(str(self.output_dir / filename2), vis2)
        
        elapsed_time = time.time() - start_time
        print(f"  ✅ Step 2: {filename2}")
        print(f"  ⏱️  Time: {elapsed_time:.3f}s")
        
        return thresh_inv, lines if lines is not None else [], elapsed_time
    
    def method4_combined(self, image: np.ndarray, mask: np.ndarray,
                        test_name: str, 
                        lines1: List, lines2: List, lines3: List) -> np.ndarray:
        """
        방법 4: Combined (하이브리드)
        모든 방법의 결과를 결합
        """
        print("\n🔍 Method 4: Combined (Hybrid)")
        
        # 모든 라인 결합
        all_lines = []
        if lines1 is not None and len(lines1) > 0:
            all_lines.extend(lines1)
        if lines2 is not None and len(lines2) > 0:
            all_lines.extend(lines2)
        if lines3 is not None and len(lines3) > 0:
            all_lines.extend(lines3)
        
        # 시각화: 모든 라인
        vis = image.copy()
        for line in all_lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(vis, (x1, y1), (x2, y2), (255, 255, 0), 1)
        
        filename = f"{test_name}_combined_all_lines.jpg"
        cv2.imwrite(str(self.output_dir / filename), vis)
        print(f"  ✅ Combined: {filename}")
        
        return vis
    
    def find_corner_refinement(self, image: np.ndarray, rough_corners: List[List[int]],
                               all_lines: List, test_name: str) -> List[List[int]]:
        """
        코너 정밀화
        각 대략적 코너 주변에서 라인 교차점 찾기
        """
        print("\n🎯 Corner Refinement")
        
        refined_corners = []
        search_radius = 50
        
        vis = image.copy()
        
        for i, rough_corner in enumerate(rough_corners):
            # 검색 영역 그리기
            cv2.rectangle(vis, 
                         (rough_corner[0] - search_radius, rough_corner[1] - search_radius),
                         (rough_corner[0] + search_radius, rough_corner[1] + search_radius),
                         (255, 0, 255), 2)
            
            # TODO: 실제 교차점 찾기 알고리즘 구현
            # 현재는 원본 코너 사용
            refined_corners.append(rough_corner)
        
        # 시각화
        filename = f"{test_name}_corner_refinement.jpg"
        cv2.imwrite(str(self.output_dir / filename), vis)
        print(f"  ✅ Refinement: {filename}")
        
        return refined_corners
    
    def run_test(self, test_case: Dict):
        """테스트 실행"""
        print(f"\n{'='*60}")
        print(f"🧪 Test: {test_case['name']}")
        print(f"{'='*60}")
        
        # 이미지 로드
        image_path = test_case['image_path']
        if not os.path.exists(image_path):
            print(f"❌ Image not found: {image_path}")
            return
        
        image = cv2.imread(image_path)
        if image is None:
            print(f"❌ Failed to load image: {image_path}")
            return
        
        print(f"📷 Image: {image_path}")
        print(f"📐 Size: {image.shape[1]}x{image.shape[0]}")
        
        # ROI 영역
        corners = test_case['area']
        print(f"📍 ROI Corners: {corners}")
        
        # ROI 시각화
        self.visualize_roi(image, corners, test_case['name'])
        
        # ROI 마스크 생성
        mask = self.create_roi_mask(image.shape, corners)
        
        # ========================================
        # 전체 이미지에 대한 검출
        # ========================================
        print(f"\n{'='*60}")
        print("🌐 FULL IMAGE DETECTION")
        print(f"{'='*60}")
        
        # 방법 1: 색상 필터링 (전체)
        _, lines1_full, time1_full = self.method1_color_filter(image, None, test_case['name'], use_roi=False)
        
        # 방법 2: Canny + Hough (전체)
        _, lines2_full, time2_full = self.method2_canny_hough(image, None, test_case['name'], use_roi=False)
        
        # 방법 3: Adaptive Threshold (전체)
        _, lines3_full, time3_full = self.method3_adaptive_threshold(image, None, test_case['name'], use_roi=False)
        
        # ========================================
        # ROI 영역에 대한 검출
        # ========================================
        print(f"\n{'='*60}")
        print("🎯 ROI AREA DETECTION")
        print(f"{'='*60}")
        
        # 방법 1: 색상 필터링 (ROI)
        _, lines1_roi, time1_roi = self.method1_color_filter(image, mask, test_case['name'], use_roi=True)
        
        # 방법 2: Canny + Hough (ROI)
        _, lines2_roi, time2_roi = self.method2_canny_hough(image, mask, test_case['name'], use_roi=True)
        
        # 방법 3: Adaptive Threshold (ROI)
        _, lines3_roi, time3_roi = self.method3_adaptive_threshold(image, mask, test_case['name'], use_roi=True)
        
        # 방법 4: Combined (ROI만 - 코너 정밀화용)
        self.method4_combined(image, mask, test_case['name'], lines1_roi, lines2_roi, lines3_roi)
        
        # 코너 정밀화 (ROI 결과 사용)
        all_lines = []
        if lines1_roi is not None:
            all_lines.extend(lines1_roi)
        if lines2_roi is not None:
            all_lines.extend(lines2_roi)
        if lines3_roi is not None:
            all_lines.extend(lines3_roi)
        
        refined_corners = self.find_corner_refinement(image, corners, all_lines, test_case['name'])
        
        print(f"\n✅ Test completed: {test_case['name']}")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"\n📊 Results Summary:")
        print(f"  - Full Image: {len(lines1_full) if lines1_full is not None else 0} + {len(lines2_full) if lines2_full is not None else 0} + {len(lines3_full) if lines3_full is not None else 0} lines")
        print(f"  - ROI Area: {len(lines1_roi) if lines1_roi is not None else 0} + {len(lines2_roi) if lines2_roi is not None else 0} + {len(lines3_roi) if lines3_roi is not None else 0} lines")
        print(f"\n⏱️  Timing Summary:")
        print(f"  Full Image:")
        print(f"    - Color Filter:  {time1_full:.3f}s")
        print(f"    - Canny + Hough: {time2_full:.3f}s")
        print(f"    - Adaptive Thr:  {time3_full:.3f}s")
        print(f"    - Total:         {time1_full + time2_full + time3_full:.3f}s")
        print(f"  ROI Area:")
        print(f"    - Color Filter:  {time1_roi:.3f}s")
        print(f"    - Canny + Hough: {time2_roi:.3f}s")
        print(f"    - Adaptive Thr:  {time3_roi:.3f}s")
        print(f"    - Total:         {time1_roi + time2_roi + time3_roi:.3f}s")
        print(f"  Grand Total:       {time1_full + time2_full + time3_full + time1_roi + time2_roi + time3_roi:.3f}s")


def main():
    """메인 함수"""
    print("🏸 Court Line Detection Test")
    print("=" * 60)
    
    # 경로 설정
    base_dir = Path(__file__).parent
    config_path = base_dir / "test_config.json"
    output_dir = base_dir / "output"
    
    # 검출기 초기화
    detector = CourtLineDetector(str(output_dir))
    
    # 설정 로드
    config = detector.load_test_case(str(config_path))
    
    # 각 테스트 케이스 실행
    for test_case in config['test_cases']:
        detector.run_test(test_case)
    
    print(f"\n{'='*60}")
    print("🎉 All tests completed!")
    print(f"📁 Results saved in: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
