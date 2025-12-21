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
        tolerance: float = 0.3
    ) -> Tuple[bool, str]:
        """
        코트 형태 유효성 검증
        
        Args:
            corners: 4개 코너
            expected_ratio: 예상 가로세로 비율 (단식 코트)
            tolerance: 허용 오차 비율
            
        Returns:
            (유효 여부, 메시지)
        """
        if len(corners) != 4:
            return False, "코너가 4개가 아닙니다"
        
        # 넓이 계산
        area = CourtGeometry.compute_court_area(corners)
        if area < 1000:  # 너무 작은 영역
            return False, "코트 영역이 너무 작습니다"
        
        # 가로세로 비율 확인
        # 간단히 바운딩 박스로 확인
        xs = [x for x, y in corners]
        ys = [y for x, y in corners]
        
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        
        if height == 0:
            return False, "높이가 0입니다"
        
        actual_ratio = height / width  # 세로가 긴 코트
        
        # 비율 검증
        min_ratio = expected_ratio * (1 - tolerance)
        max_ratio = expected_ratio * (1 + tolerance)
        
        if actual_ratio < min_ratio or actual_ratio > max_ratio:
            return False, f"코트 비율이 부적절합니다 (expected: {expected_ratio:.2f}, actual: {actual_ratio:.2f})"
        
        return True, "유효한 코트 형태입니다"