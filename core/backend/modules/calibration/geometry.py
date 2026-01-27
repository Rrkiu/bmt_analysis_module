"""
기하학 연산 모듈
- Homography 변환
- 좌표 변환
- 투영 변환
"""

import numpy as np
import cv2
from typing import Tuple, Optional, List


class HomographyTransform:
    """Homography 변환 클래스"""
    
    def __init__(self):
        self.homography_matrix: Optional[np.ndarray] = None
        self.inv_homography_matrix: Optional[np.ndarray] = None
    
    def compute_homography(
        self, 
        src_points: np.ndarray, 
        dst_points: np.ndarray,
        method: int = cv2.RANSAC
    ) -> bool:
        """
        Homography 행렬 계산
        
        Args:
            src_points: 소스 좌표 (N, 2) - 이미지 좌표계
            dst_points: 목적지 좌표 (N, 2) - 실세계 좌표계
            method: OpenCV homography 계산 방법
            
        Returns:
            bool: 계산 성공 여부
        """
        if len(src_points) < 4 or len(dst_points) < 4:
            return False
        
        if len(src_points) != len(dst_points):
            return False
        
        # Homography 행렬 계산
        self.homography_matrix, mask = cv2.findHomography(
            src_points, 
            dst_points, 
            method,
            ransacReprojThreshold=5.0
        )
        
        if self.homography_matrix is None:
            return False
        
        # 역변환 행렬도 계산
        self.inv_homography_matrix = np.linalg.inv(self.homography_matrix)
        
        return True
    
    def image_to_world(self, image_point: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """
        이미지 좌표 → 실세계 좌표 변환
        
        Args:
            image_point: (x, y) 이미지 픽셀 좌표
            
        Returns:
            (x, y) 실세계 좌표 (미터) 또는 None
        """
        if self.homography_matrix is None:
            return None
        
        # Homogeneous 좌표로 변환
        point = np.array([[image_point[0], image_point[1]]], dtype=np.float32)
        
        # 변환
        transformed = cv2.perspectiveTransform(
            point.reshape(-1, 1, 2), 
            self.homography_matrix
        )
        
        return (float(transformed[0][0][0]), float(transformed[0][0][1]))
    
    def world_to_image(self, world_point: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """
        실세계 좌표 → 이미지 좌표 변환
        
        Args:
            world_point: (x, y) 실세계 좌표 (미터)
            
        Returns:
            (x, y) 이미지 픽셀 좌표 또는 None
        """
        if self.inv_homography_matrix is None:
            return None
        
        point = np.array([[world_point[0], world_point[1]]], dtype=np.float32)
        
        transformed = cv2.perspectiveTransform(
            point.reshape(-1, 1, 2),
            self.inv_homography_matrix
        )
        
        return (float(transformed[0][0][0]), float(transformed[0][0][1]))
    
    def transform_points(
        self, 
        points: List[Tuple[float, float]], 
        to_world: bool = True
    ) -> List[Tuple[float, float]]:
        """
        여러 점을 한번에 변환
        
        Args:
            points: 변환할 점들의 리스트
            to_world: True면 image→world, False면 world→image
            
        Returns:
            변환된 점들의 리스트
        """
        results = []
        transform_func = self.image_to_world if to_world else self.world_to_image
        
        for point in points:
            transformed = transform_func(point)
            if transformed:
                results.append(transformed)
        
        return results
    
    def get_reprojection_error(
        self, 
        src_points: np.ndarray, 
        dst_points: np.ndarray
    ) -> float:
        """
        재투영 오차 계산 (정확도 평가용)
        
        Args:
            src_points: 소스 좌표
            dst_points: 목적지 좌표
            
        Returns:
            평균 재투영 오차 (픽셀)
        """
        if self.homography_matrix is None:
            return float('inf')
        
        # 변환된 점 계산
        src_points_reshaped = src_points.reshape(-1, 1, 2).astype(np.float32)
        projected_points = cv2.perspectiveTransform(
            src_points_reshaped,
            self.homography_matrix
        )
        
        # 유클리드 거리 계산
        errors = np.sqrt(
            np.sum((projected_points.reshape(-1, 2) - dst_points) ** 2, axis=1)
        )
        
        return float(np.mean(errors))


class CourtGeometry:
    """코트 기하학 연산"""
    
    @staticmethod
    def scale_to_pixels(
        real_points: List[Tuple[float, float]],
        scale: float = 100.0
    ) -> List[Tuple[float, float]]:
        """
        실세계 좌표를 픽셀 좌표로 스케일링
        
        Args:
            real_points: 실세계 좌표 (미터)
            scale: 1미터 = scale 픽셀
            
        Returns:
            픽셀 좌표
        """
        return [(x * scale, y * scale) for x, y in real_points]
    
    @staticmethod
    def get_court_polygon_from_corners(
        corners: List[Tuple[float, float]]
    ) -> np.ndarray:
        """
        4개 코너로부터 폴리곤 생성
        
        Args:
            corners: [top_left, top_right, bottom_right, bottom_left]
            
        Returns:
            OpenCV 폴리곤 형태 (N, 1, 2)
        """
        return np.array(corners, dtype=np.int32).reshape((-1, 1, 2))
    
    @staticmethod
    def compute_court_area(corners: List[Tuple[float, float]]) -> float:
        """
        코트 영역 넓이 계산
        
        Args:
            corners: 4개 코너 좌표
            
        Returns:
            넓이 (제곱미터 또는 제곱픽셀)
        """
        polygon = np.array(corners, dtype=np.float32)
        area = cv2.contourArea(polygon)
        return float(area)
    
    @staticmethod
    def is_valid_court_shape(
        corners: List[Tuple[float, float]],
        expected_ratio: float = 13.4 / 5.18,
        tolerance: float = 0.8  # [수정됨] 0.3 → 0.8 (더 관대하게)
    ) -> Tuple[bool, str]:
        """
        코트 형태 유효성 검증
        
        [수정됨 - 2025-12-23]
        4점 직접 선택 방식에서는 Homography가 모든 왜곡을 처리하므로
        비율 검증을 완화함. 주로 명백한 오류만 검출.
        
        Args:
            corners: 4개 코너
            expected_ratio: 예상 가로세로 비율 (참고용)
            tolerance: 허용 오차 비율 (0.8 = ±80%)
            
        Returns:
            (유효 여부, 메시지)
        """
        if len(corners) != 4:
            return False, "코너가 4개가 아닙니다"
        
        # 넓이 계산
        area = CourtGeometry.compute_court_area(corners)
        if area < 1000:  # 너무 작은 영역
            return False, "코트 영역이 너무 작습니다"
        
        # [수정됨] 비율 검증 완화
        # 가로세로 비율 확인 (바운딩 박스 기준)
        xs = [x for x, y in corners]
        ys = [y for x, y in corners]
        
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        
        if height == 0 or width == 0:
            return False, "코트 크기가 0입니다"
        
        # 비율 계산 (세로/가로 또는 가로/세로 중 큰 값)
        ratio = max(height / width, width / height)
        
        # 극단적인 경우만 거부 (예: 10:1 이상)
        if ratio > 10.0:
            return False, f"코트 비율이 극단적입니다 (ratio: {ratio:.2f})"
        
        # [수정됨] 대부분의 경우 통과
        return True, "유효한 코트 형태입니다"

    @staticmethod
    def is_point_in_court(world_point: Tuple[float, float], margin: float = 0.0) -> bool:
        """
        실세계 좌표가 유효 코트 영역 내에 있는지 확인 (단식 코트 기준)
        
        Args:
            world_point: (x, y) 실세계 좌표 (미터)
            margin: 허용 마진 (미터)
            
        Returns:
            bool: 코트 내 여부
        """
        from constants import CourtDimensions
        
        x, y = world_point
        half_width = CourtDimensions.SINGLES_WIDTH / 2
        
        # x: -half_width ~ half_width
        # y: 0 ~ BACK_BOUNDARY_LINE (6.7m)
        in_x = (-half_width - margin) <= x <= (half_width + margin)
        in_y = (0 - margin) <= y <= (CourtDimensions.BACK_BOUNDARY_LINE + margin)
        
        return in_x and in_y